#!/usr/bin/env node
/**
 * Seed the behavioral layer (business_rules + connectors) into the nexus PenFiles.
 *
 * The ERDs (*.dfd.json `erd`) capture structure; this populates the `dfd.business_rules` and
 * `dfd.connectors` arrays — the invariants/gates/state-machines and the cross-service seams/middleware
 * that the structure can't express. Single source of truth for that content; re-run to update.
 *
 *   node demo-site/scripts/seed-nexus-behavior.mjs
 *
 * Idempotent: overwrites the two arrays on each nexus file. Connectors live in full on 00_nexus_master
 * (the cross-context map); each context file gets the connectors that originate from or target it.
 * Every rule/connector carries `enforced_at` (NexusPlatform code file:line) for traceability.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const NX = resolve(dirname(fileURLToPath(import.meta.url)), "../frontend/public/nexus");

// ── Cross-service connectors / middleware (the 7 seams + shared middleware) ──────────────────────────
const CONNECTORS = [
  { id: "conn_seam1_control_numbers", name: "Seam 1 — Control-Number authority", kind: "shared_service",
    trigger: "Any context mints a traceable record", effect: "A single immutable control number ({prefix}{YYMMDD}-{genocode}, 18 type codes) is issued and never edited/deleted",
    from_context: "02_control_numbers", to_contexts: ["03_genetics", "04_cultivation_harvest", "05_refinement_packaging", "06_qa_lab", "07_quality_batch"],
    contract: "ControlNumberService.create(type, facilityPrefix, genocode, date) -> value",
    enforced_at: ["backend/src/contexts/control-numbers/domain/control-number.ts:36-66", "backend/src/contexts/control-numbers/service/control-number-service.ts:18-32"],
    spec_source: "40-unified-workflow-graph.md (Seam 1); spec-control-numbers.md", status: "wired", review_status: "accepted" },

  { id: "conn_seam2_reconciliation_gate", name: "Seam 2 — Batch release reconciliation gate", kind: "seam",
    trigger: "POST /api/quality/batches/:id/reconcile with a 6-dimension mismatch", effect: "Batch moves to `hold` AND an incident ticket is auto-created (severity high)",
    from_context: "05_refinement_packaging", to_contexts: ["07_quality_batch"],
    contract: "{ controlNumber, chemistry, quantity, lineage, product, status } each {expected,actual} -> {batch, reconciliation:{passed,mismatches}, incident}",
    enforced_at: ["backend/src/index.ts:1236-1261", "backend/src/contexts/quality/domain/batch.ts:161-209"],
    spec_source: "04-batch-reconciliation.md §56-81", status: "wired", review_status: "accepted" },

  { id: "conn_seam3_lims_fanout", name: "Seam 3 — LIMS webhook fan-out", kind: "fan_out",
    trigger: "POST /api/qa-lab/lims-webhook (single lab writer)", effect: "Creates a test-run + records cannabinoid/terpene results AND seeds a consumer-profile (PhytoFacts) from the same payload",
    from_context: "06_qa_lab", to_contexts: ["06_qa_lab", "09_consumer_profile"],
    contract: "{ facilityPrefix, genocode, sample.testId, cannabinoids, terpenes } -> { labResults, consumerProfile }",
    enforced_at: ["backend/src/index.ts:891-931"],
    spec_source: "40-unified-workflow-graph.md (Seam 3); spec-workflow-qa.md §4", status: "wired", review_status: "accepted" },

  { id: "conn_seam4_genocode_authority", name: "Seam 4 — Genocode / product master authority", kind: "shared_service",
    trigger: "Product + strain references resolved", effect: "Genocode is the authority; product-master unifies the legacy batch.Product + SpecProduct models",
    from_context: "08_product_master", to_contexts: ["03_genetics", "07_quality_batch", "09_consumer_profile"],
    contract: "genocode -> product_id mapping (canonical)",
    enforced_at: ["backend/src/contexts/product-master/service/product-master-service.ts"],
    spec_source: "40-unified-workflow-graph.md (Seam 4)", status: "deferred", review_status: "needs_review" },

  { id: "conn_seam6_sso_allowlist", name: "Seam 6 — SSO + company-domain allowlist", kind: "auth",
    trigger: "User login", effect: "Email domain checked against the active CompanyDomainAllowlist before any user/session is created; role tiers applied",
    from_context: "01_identity", to_contexts: ["01_identity"],
    contract: "isAllowedEmail(email) throws if domain not allowlisted; roles admin/quality/manager/operator + sales/facility-op/lab-tech",
    enforced_at: ["backend/src/contexts/identity/service/identity-service.ts:51-59"],
    spec_source: "40-unified-workflow-graph.md (Seam 6); 30-nexus-intel.md", status: "wired", review_status: "accepted" },

  { id: "conn_seam7_shared_ai", name: "Seam 7 — Shared AI service (PII-stripped, provider fallback)", kind: "shared_service",
    trigger: "Any context requests AI assistance (SOP/CAPA, sales copy, consumer copy)", effect: "callAiWithFallback strips customer PII + enforces spend cap (Anthropic -> Groq fallback)",
    from_context: "11_finance_ai", to_contexts: ["07_quality_batch", "09_consumer_profile", "10_sales"],
    contract: "callAiWithFallback(prompt) with stripCustomerPII + spend-cap",
    enforced_at: ["(not built — finance/ai/* scaffold only)"],
    spec_source: "40-unified-workflow-graph.md (Seam 7); 30-nexus-intel.md", status: "deferred", review_status: "needs_review" },

  { id: "conn_harvest_finish_cn", name: "Harvest FINISHED → control-number finish", kind: "seam",
    trigger: "Harvest phase transitions to FINISHED (40)", effect: "The harvest's control number is stamped finished (is_finished/finishedAt) — forward, no double-finish",
    from_context: "04_cultivation_harvest", to_contexts: ["02_control_numbers"],
    contract: "transitionHarvestPhase(id, FINISHED) -> controlNumberService.finish(harvest.controlNumber, now)",
    enforced_at: ["backend/src/contexts/cultivation/service/cultivation-service.ts:225-228"],
    spec_source: "spec-workflow-harvest.md §56-57", status: "wired", review_status: "accepted" },

  { id: "conn_mw_503_guard", name: "Middleware — DATABASE_URL service guard", kind: "middleware",
    trigger: "Any data route invoked", effect: "Routes return 503 when their service wasn't built (DATABASE_URL unset) — graceful degradation",
    from_context: "00_nexus_master", to_contexts: [],
    contract: "if(!svc){ sendJson(res,503,{error:'<ctx> requires DATABASE_URL'}); return; }",
    enforced_at: ["backend/src/index.ts (per-route guard pattern)"],
    spec_source: "AGENTS.md §5/§9", status: "wired", review_status: "accepted" },

  { id: "conn_mw_http_util", name: "Middleware — shared HTTP helpers", kind: "middleware",
    trigger: "Every request/response", effect: "Stream JSON parse (parseBody), typed JSON write (sendJson), Bearer extraction (getAuthHeader), control-number inference helpers",
    from_context: "00_nexus_master", to_contexts: [],
    contract: "parseBody<T> | sendJson | getAuthHeader | normalizeControlNumberPart",
    enforced_at: ["backend/src/http-util.ts"],
    spec_source: "AGENTS.md §9", status: "wired", review_status: "accepted" },

  { id: "conn_mw_session", name: "Middleware — session validation", kind: "auth",
    trigger: "Authenticated route invoked", effect: "Bearer session id resolved to the current user/session via identity service",
    from_context: "01_identity", to_contexts: [],
    contract: "getAuthHeader(req) -> identityService.currentSession(sessionId)",
    enforced_at: ["backend/src/index.ts (currentSession wiring)", "backend/src/contexts/identity/service/identity-service.ts"],
    spec_source: "AGENTS.md §9", status: "wired", review_status: "accepted" },
];

// ── Business rules per context ───────────────────────────────────────────────────────────────────────
const BP = "docs/context/behavioral-parity.md";
const r = (o) => ({ severity: "constraint", status: "enforced", review_status: "accepted", enforced_at: [], to_contexts: [], ...o });

const RULES = {
  "02_control_numbers": [
    r({ id: "CN-INV-01", title: "Immutable after creation", category: "invariant",
        statement: "Control numbers are never edited or deleted — only marked finished. finishControlNumber returns a NEW frozen object.",
        condition: "Object.freeze; finish creates new object", enforced_at: ["backend/src/contexts/control-numbers/domain/control-number.ts:36-66"],
        spec_source: "spec-control-numbers.md §54-58", verified_by: BP + " (control-numbers: Immutability invariant)" }),
    r({ id: "CN-INV-02", title: "No double-finish", category: "invariant",
        statement: "Finishing an already-finished control number is rejected.", condition: "throw if cn.finishedAt !== null",
        enforced_at: ["backend/src/contexts/control-numbers/domain/control-number.ts:62-64"], spec_source: "spec-control-numbers.md", verified_by: BP + " (No double-finish)" }),
    r({ id: "CN-INV-03", title: "18 fixed type codes", category: "invariant",
        statement: "Exactly 18 control-number types (PLANT_LOT=1 … PACKAGE=18) with fixed IDs.",
        enforced_at: ["shared/src/control-number.ts:13-32"], spec_source: "spec-control-numbers.md §29-50", verified_by: BP + " (18 type codes)" }),
    r({ id: "CN-VAL-01", title: "Format {facilityPrefix}{YYMMDD}-{genocode}", category: "validation",
        statement: "Value composes facility prefix + YYMMDD date + genocode, with optional .NN sub-unit sequence and -SUFFIX (e.g. -HVST).",
        enforced_at: ["backend/src/contexts/control-numbers/domain/control-number.ts:43-45"], spec_source: "spec-control-numbers.md §20-27", verified_by: BP + " (Format pattern)" }),
  ],
  "03_genetics": [
    r({ id: "GEN-INV-01", title: "Per-entity control-number types", category: "invariant",
        statement: "GeneLot=9, GeneLotPlant=10, SeedExperiment=11, SeedLot=12, SeedLotPlant=14, GermLot(GNBR)=15.",
        enforced_at: ["backend/src/contexts/genetics/service/genetics-service.ts"], spec_source: "spec-workflow-genetics.md", verified_by: BP + " (genetics: CN types)" }),
    r({ id: "GEN-INV-02", title: "Cull is immutable", category: "invariant",
        statement: "cullGeneLot/cullSeedExperiment return NEW frozen objects with isCulled=true; originals never mutated.",
        enforced_at: ["backend/src/contexts/genetics/domain/genetics.ts:351-372"], spec_source: "spec-workflow-genetics.md §45", verified_by: BP + " (Cull semantics)" }),
    r({ id: "GEN-VAL-01", title: "SeedLot requires donor + target lineage", category: "validation",
        statement: "Creating a SeedLot requires both targetGeneLotId and donorGeneLotId; the service verifies both exist.",
        enforced_at: ["backend/src/contexts/genetics/domain/genetics.ts:220-237", "backend/src/contexts/genetics/service/genetics-service.ts:227-233"], spec_source: "spec-workflow-genetics.md §55", verified_by: BP + " (SeedLot lineage)" }),
    r({ id: "GEN-GAP-01", title: "CloneLot.numberOfClones decrement", category: "invariant", severity: "warning", status: "gap",
        statement: "Spec: creating a gene lot from a clone lot decrements clone_lot.number_of_clones by N. cloneLotRepo is now injected, but the decrement is not yet applied.",
        enforced_at: ["backend/src/contexts/genetics/service/genetics-service.ts (createGeneLot)"], spec_source: "spec-workflow-genetics.md §32", verified_by: BP + " (genetics GAP)" }),
    r({ id: "GEN-GAP-02", title: "ChemocodeFuser", category: "invariant", severity: "warning", status: "gap",
        statement: "Spec: fuse chemotype data onto gene lots (ChemocodeFuser). Not implemented.",
        enforced_at: [], spec_source: "spec-workflow-genetics.md §70", verified_by: BP + " (genetics GAP)" }),
  ],
  "04_cultivation_harvest": [
    r({ id: "CUL-SM-01", title: "Plant-lot phase machine (forward-only)", category: "state_machine",
        statement: "VEGETATIVE(1)→FLOWER(2)→DRY(3)→FINISHED(4); each step stamps its date; invalid transitions throw.",
        enforced_at: ["backend/src/contexts/cultivation/domain/cultivation.ts:130-186"], spec_source: "spec-workflow-harvest.md §47-56", verified_by: BP + " (cultivation: plant-lot phase machine)" }),
    r({ id: "CUL-SM-02", title: "Harvest phase machine (forward-only)", category: "state_machine",
        statement: "DRYING(10)→CURING(20)→PROCESSING(30)→FINISHED(40); date-stamped; forward-only.",
        enforced_at: ["backend/src/contexts/cultivation/domain/cultivation.ts:287-343"], spec_source: "spec-workflow-harvest.md §49-54", verified_by: BP + " (harvest phase machine)" }),
    r({ id: "CUL-INV-01", title: "Waste log is append-only", category: "invariant",
        statement: "Harvest waste is append-only; a BEFORE UPDATE/DELETE trigger blocks mutation.",
        enforced_at: ["db/migrations/0004_cultivation_harvest.sql:103-149"], spec_source: "spec-workflow-harvest.md §58", verified_by: BP + " (Waste tracking)" }),
    r({ id: "CUL-LC-01", title: "Harvest FINISHED finishes the control number", category: "lifecycle",
        statement: "Reaching FINISHED stamps the harvest control number finished (see Seam: harvest-finish-cn).",
        enforced_at: ["backend/src/contexts/cultivation/service/cultivation-service.ts:225-228"], spec_source: "spec-workflow-harvest.md §56-57", verified_by: BP + " (cultivation 8/2)" }),
    r({ id: "CUL-GAP-01", title: "Tracking-location move (BTX/BTF)", category: "lifecycle", severity: "warning", status: "gap",
        statement: "Spec: changeTrackingLocation moves the harvest AND its BTX/BTF bags atomically. Not implemented (blocked on packaging context).",
        enforced_at: [], spec_source: "spec-workflow-harvest.md §62-63", verified_by: BP + " (cultivation GAP)" }),
  ],
  "06_qa_lab": [
    r({ id: "QA-SM-01", title: "Test-run phase ordering (forward-only)", category: "state_machine",
        statement: "SUBMISSIONS→TEST_PREP→ACTIVE→AWAITING_RESULTS→FINISHED; cannot move backward; cannot re-finish.",
        enforced_at: ["backend/src/contexts/qa-lab/domain/test-run.ts:51-91"], spec_source: "spec-workflow-qa.md", verified_by: BP + " (qa-lab 16/0)" }),
    r({ id: "QA-VAL-01", title: "Chemistry values are strings (DECIMAL)", category: "validation",
        statement: "Cannabinoid/terpene results are decimal strings (e.g. \"15.5\"), never numbers — passing numbers throws.",
        enforced_at: ["shared/src/qa-lab.ts:214-303"], spec_source: "spec-workflow-qa.md", verified_by: "AGENTS.md §9 (gotchas)" }),
    r({ id: "QA-VAL-02", title: "16-analyte cannabinoid + 8-analyte terpene panels", category: "validation",
        statement: "Cannabinoid panel = 16 analytes (acid+neutral forms); terpene panel = representative 8-analyte subset.",
        enforced_at: ["shared/src/qa-lab.ts:214-287"], spec_source: "spec-workflow-qa.md", verified_by: BP + " (qa-lab panels)" }),
    r({ id: "QA-INV-01", title: "Results are append-only", category: "invariant",
        statement: "Cannabinoid/terpene result rows are immutable (1:1 per sample, no updates); DB triggers enforce.",
        enforced_at: ["db/migrations/0006_qa_lab.sql"], spec_source: "spec-workflow-qa.md", verified_by: BP + " (qa-lab immutability)" }),
  ],
  "07_quality_batch": [
    r({ id: "QB-GATE-01", title: "6-dimension release reconciliation gate", category: "gate",
        statement: "At release, control#, chemistry, quantity, lineage, product, status are each checked expected-vs-actual; all must match to pass.",
        condition: "reconcileBatch(input).passed === mismatches.length === 0", enforced_at: ["backend/src/contexts/quality/domain/batch.ts:161-209"], spec_source: "04-batch-reconciliation.md §56-81", verified_by: "Seam 2; index.ts:1236-1261" }),
    r({ id: "QB-GATE-02", title: "Reconcile-fail → hold + auto-incident", category: "gate",
        statement: "Any mismatch holds the batch AND auto-creates a high-severity incident ('flag, don't silently sync').",
        enforced_at: ["backend/src/index.ts:1244-1255"], spec_source: "04-batch-reconciliation.md §72-80", verified_by: "missing-functionality-backlog.md (P0 #1)" }),
    r({ id: "QB-SM-01", title: "Batch status machine", category: "state_machine",
        statement: "REVIEW→{APPROVED|HOLD}; HOLD→{REMEDIATION|DESTRUCTION|REVIEW}; REMEDIATION→REVIEW; APPROVED/DESTRUCTION terminal.",
        enforced_at: ["backend/src/contexts/quality/domain/batch.ts:52-74"], spec_source: "20-qms-platform.md §146-168", verified_by: BP }),
    r({ id: "QB-SM-02", title: "Incident pipeline", category: "state_machine",
        statement: "open→classification→investigation→disposition→capa→closed→archived (forward advance).",
        enforced_at: ["backend/src/contexts/quality/service/incident-service.ts"], spec_source: "20-qms-platform.md §204-242", verified_by: "missing-functionality-backlog.md (P0 #2)" }),
    r({ id: "QB-GATE-03", title: "Product-verification checkpoint + hold", category: "gate",
        statement: "PV logs accumulate checkpoints; placing a hold at a checkpoint transitions the log to 'hold'.",
        enforced_at: ["backend/src/index.ts (product-verification routes)", "backend/src/contexts/quality/service/product-verification-service.ts"], spec_source: "20-qms-platform.md §181-202", verified_by: "missing-functionality-backlog.md (P0 #3)" }),
    r({ id: "QB-LC-01", title: "Statement & change-control lifecycles", category: "lifecycle",
        statement: "Statements: draft→in_review→effective→superseded/obsolete. Change-controls: draft→pending_approval→approved/rejected→implemented→closed.",
        enforced_at: ["backend/src/contexts/quality/service/statement-service.ts", "backend/src/contexts/quality/service/change-control-service.ts"], spec_source: "20-qms-platform.md", verified_by: BP }),
    r({ id: "QB-INV-01", title: "Document versions are immutable", category: "invariant",
        statement: "Document versions are never edited/deleted, only superseded (append-only version chain).",
        enforced_at: ["backend/src/contexts/quality/domain/document-version.ts"], spec_source: "20-qms-platform.md §68-111", verified_by: "AGENTS.md §6 (reliability bar)" }),
  ],
  "01_identity": [
    r({ id: "ID-GATE-01", title: "Company-domain allowlist gate", category: "gate",
        statement: "An email's domain must be on the active CompanyDomainAllowlist BEFORE any user/session is created.",
        enforced_at: ["backend/src/contexts/identity/domain/domain-allowlist.ts", "backend/src/contexts/identity/service/identity-service.ts:51-59"], spec_source: "30-nexus-intel.md (SSO)", verified_by: "Seam 6 (conn_seam6_sso_allowlist)" }),
    r({ id: "TEN-VAL-01", title: "Facility control-number prefix authority", category: "validation",
        statement: "Each facility owns a control-number prefix; control numbers compose it as {facilityPrefix}{YYMMDD}-{genocode}.",
        enforced_at: ["shared/src/tenancy.ts", "backend/src/contexts/tenancy/"], spec_source: "spec-control-numbers.md" }),
  ],
  "05_refinement_packaging": [
    r({ id: "REF-INV-01", title: "Output packages get PACKAGE (18) control numbers", category: "invariant",
        statement: "Each refinement output package obtains a ControlNumberType.PACKAGE (18) control number.",
        enforced_at: ["backend/src/contexts/refinement/service/refinement-service.ts:139-141"], spec_source: "spec-workflow-refinement.md §24", verified_by: BP + " (refinement)" }),
    r({ id: "REF-INV-02", title: "Refinement runs are append-only/immutable", category: "invariant",
        statement: "A refinement run is immutable once created — outputs and waste are append-only additions, never edits.",
        enforced_at: ["backend/src/contexts/refinement/service/refinement-service.ts:8"], spec_source: "spec-workflow-refinement.md", verified_by: BP + " (Run immutability)" }),
    r({ id: "REF-LC-01", title: "Input bulk package → outputs + parent→child lineage", category: "lifecycle",
        statement: "executeRefinement consumes a bulk input package and produces output packages, linking parent→child lineage rows; waste is tracked separately.",
        enforced_at: ["backend/src/contexts/refinement/service/refinement-service.ts:116-213"], spec_source: "spec-workflow-refinement.md §16,63-86", verified_by: BP + " (refinement lineage)" }),
    r({ id: "REF-VAL-01", title: "Yield is derived, not stored", category: "validation", severity: "best_practice",
        statement: "Yield % = sum(output amounts) / input_amount, computed on read from stored amounts (not persisted).",
        enforced_at: ["backend/src/contexts/refinement/service/refinement-service.ts"], spec_source: "spec-workflow-refinement.md §98", verified_by: BP + " (yield derivable)" }),
  ],
  "08_product_master": [
    r({ id: "PM-INV-01", title: "Products are immutable after creation", category: "invariant",
        statement: "Product records (and document versions) are frozen at creation — immutable at type and runtime level.",
        enforced_at: ["backend/src/contexts/product-master/domain/product.ts:5,42"], spec_source: "06-production-and-costing.md", verified_by: "AGENTS.md §6" }),
    r({ id: "PM-SM-01", title: "DD project gate state machine", category: "state_machine",
        statement: "Design & Development projects advance through gates: draft→in_review→work_proposal→execution→outcome→completed (or closed_no_go).",
        enforced_at: ["backend/src/contexts/product-master/service/product-master-service.ts (advanceDdProjectGate)", "shared/src/product-master.ts:12-22"], spec_source: "06-production-and-costing.md" }),
    r({ id: "PM-VAL-01", title: "SKU is a documented surrogate", category: "validation", severity: "best_practice",
        statement: "`sku` is a domain-view surrogate with no persisted ERD column (allow-listed in endpoint-parity).",
        enforced_at: ["scripts/endpoint-parity.mjs (ALLOW_EXTRA)"], spec_source: "data-model.md" }),
    r({ id: "PM-GAP-01", title: "Genocode authority (redesign)", category: "invariant", severity: "warning", status: "gap",
        statement: "Genocode should be the canonical product/strain authority unifying the legacy models (Seam 4). Redesign pending.",
        enforced_at: [], spec_source: "40-unified-workflow-graph.md (Seam 4)", verified_by: "missing-functionality-backlog.md (P2 #12)" }),
  ],
  "09_consumer_profile": [
    r({ id: "CP-INV-01", title: "Consumer profiles immutable (archive-only)", category: "invariant",
        statement: "A generated PhytoFacts profile is immutable after creation — never edited, only archived.",
        enforced_at: ["backend/src/contexts/consumer-profile/domain/consumer-profile.ts:5,56"], spec_source: "11-phytofacts.md", verified_by: "AGENTS.md §6" }),
    r({ id: "CP-VAL-01", title: "PhytoFacts calculators", category: "validation",
        statement: "Four pure calculators derive the profile: top-two cannabinoid ratio, top-three terpene colors, entourage summary, organoleptic descriptors.",
        enforced_at: ["backend/src/contexts/consumer-profile/domain/calculators.ts"], spec_source: "11-phytofacts.md", verified_by: "/api/consumer-profile/compute" }),
  ],
  "10_sales": [
    r({ id: "SAL-INV-01", title: "Sales records are immutable (frozen)", category: "invariant",
        statement: "Accounts, contacts, deals, and meetings are frozen at creation (readonly + Object.freeze).",
        enforced_at: ["backend/src/contexts/sales/domain/contact.ts:28-41"], spec_source: "30-nexus-intel.md", verified_by: "AGENTS.md §6" }),
    r({ id: "SAL-LC-01", title: "Intel sales breadth deprioritized", category: "lifecycle", severity: "best_practice", status: "deferred",
        statement: "The ~80-endpoint Intel sales breadth (HubSpot/shipping/lead-gen/etc.) is descoped by the product owner; the core sales entities exist.",
        enforced_at: [], spec_source: "missing-functionality-backlog.md (P2 #14)" }),
  ],
  "11_finance_ai": [
    r({ id: "FIN-INV-01", title: "Revenue immutable after close", category: "invariant",
        statement: "A revenue record is immutable once isClosed=true.",
        enforced_at: ["backend/src/contexts/finance/domain/revenue.ts:7,35"], spec_source: "06-production-and-costing.md", verified_by: "AGENTS.md §6" }),
    r({ id: "FIN-LC-01", title: "Accounting stays in Sage (CSV export boundary)", category: "lifecycle",
        statement: "Cost/accounting lives in Sage; Nexus only exports an activity CSV — it does not own the ledger.",
        enforced_at: ["backend/src/contexts/finance/http.ts (/api/finance/export)"], spec_source: "project-brief.md; AGENTS.md §2" }),
  ],
};

// ── Patch each nexus file ──────────────────────────────────────────────────────────────────────────
const CONTEXT_KEYS = [
  "00_nexus_master", "01_identity", "02_control_numbers", "03_genetics", "04_cultivation_harvest",
  "05_refinement_packaging", "06_qa_lab", "07_quality_batch", "08_product_master",
  "09_consumer_profile", "10_sales", "11_finance_ai",
];

let patched = 0;
for (const key of CONTEXT_KEYS) {
  const file = `${NX}/${key}.dfd.json`;
  if (!existsSync(file)) { console.log(`skip  ${key} (not found)`); continue; }
  const pen = JSON.parse(readFileSync(file, "utf8"));
  if (!pen.dfd || typeof pen.dfd !== "object") { console.log(`skip  ${key} (no dfd block)`); continue; }

  const rules = RULES[key] ?? [];
  const connectors = key === "00_nexus_master"
    ? CONNECTORS
    : CONNECTORS.filter((c) => c.from_context === key || c.to_contexts.includes(key));

  pen.dfd.business_rules = rules;
  pen.dfd.connectors = connectors;
  writeFileSync(file, JSON.stringify(pen, null, 2) + "\n");
  console.log(`ok    ${key}  rules=${rules.length} connectors=${connectors.length}`);
  patched++;
}
console.log(`\nPatched ${patched} nexus files.`);
