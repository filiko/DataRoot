"""V2 — cross-system seam detection + business-rule grounding (SaaS A/B/C)."""
from __future__ import annotations

from dataroot.systemmap import (
    BusinessRule,
    Evidence,
    Ref,
    SystemMap,
    detect_cross_system_seams,
    generic_saas_abc_map,
    ground_business_rules,
)
from dataroot.systemmap.models import (
    AccessSurface,
    DataField,
    DataObject,
    EnterpriseSystem,
)
from dataroot.systemmap.seams import _referenced_base


def _ev() -> Evidence:
    return Evidence(id="ev_test", kind="manual", locator="manual://test", excerpt="test", confidence=0.9)


def _without_connectors(m: SystemMap) -> SystemMap:
    """Same map but no connectors (and flow.via cleared so it still validates)."""
    return SystemMap(
        systems=m.systems,
        access_surfaces=m.access_surfaces,
        data_objects=m.data_objects,
        data_fields=m.data_fields,
        business_rules=m.business_rules,
        connectors=[],
        data_flows=[f.model_copy(update={"via": None}) for f in m.data_flows],
    )


def _with_rules(m: SystemMap, rules: list[BusinessRule]) -> SystemMap:
    data = m.model_dump()
    data["business_rules"] = [r.model_dump() for r in rules]
    return SystemMap.model_validate(data)


# ── seam detection ────────────────────────────────────────────────────────────

def test_detects_order_device_seam_when_no_connector() -> None:
    seams = detect_cross_system_seams(_without_connectors(generic_saas_abc_map()))
    assert len(seams) == 1
    seam = seams[0]
    assert seam.kind == "seam"
    assert seam.from_system == "saas_c" and seam.to_systems == ["saas_b"]
    assert seam.review_status == "needs_review"  # decision #5: never auto-asserted
    assert "device_id" in (seam.contract or "").lower()


def test_no_duplicate_seam_when_connector_already_covers_it() -> None:
    # Full fixture already has a hand-authored Order→Device connector.
    assert detect_cross_system_seams(generic_saas_abc_map()) == []


def test_no_seam_for_same_system_or_unmatched_field() -> None:
    # Device.device_id is same-system; Order.customer_id has no Customer object.
    seams = detect_cross_system_seams(_without_connectors(generic_saas_abc_map()))
    contracts = " ".join((s.contract or "") for s in seams).lower()
    assert "customer" not in contracts
    assert "device.device_id" not in contracts  # the same-system one is not a seam


# ── grounding ─────────────────────────────────────────────────────────────────

def _order_rule(statement: str) -> BusinessRule:
    return BusinessRule(
        id="rule_order_x", scope=Ref(kind="object", id="object_order"),
        title="Order rule", statement=statement, category="invariant",
        evidence=[_ev()], confidence=0.9, review_status="accepted",
    )


def test_grounding_single_system_for_device_rule() -> None:
    groundings = {g.rule_id: g for g in ground_business_rules(generic_saas_abc_map())}
    assert groundings["rule_n9102_status_values"].classification == "single_system"


def test_grounding_cross_system_grounded_via_connector() -> None:
    m = _with_rules(generic_saas_abc_map(), [_order_rule("Every order must reference a valid Device.")])
    g = ground_business_rules(m)[0]
    assert g.classification == "cross_system_grounded"
    assert g.connector_id and set(g.systems) == {"saas_c", "saas_b"}


def test_grounding_cross_system_grounded_via_detected_seam_without_connector() -> None:
    # No explicit connector, but Order.device_id seam still grounds the rule.
    m = _without_connectors(_with_rules(generic_saas_abc_map(),
                                        [_order_rule("Every order must reference a valid Device.")]))
    g = ground_business_rules(m)[0]
    assert g.classification == "cross_system_grounded"


def test_grounding_cross_system_gap_when_nothing_links_systems() -> None:
    # Order rule references ThetaReading (SaaS A) — no field seam, no connector.
    m = _with_rules(generic_saas_abc_map(), [_order_rule("Each order must be linked to a ThetaReading.")])
    g = ground_business_rules(m)[0]
    assert g.classification == "cross_system_gap"
    assert set(g.systems) == {"saas_c", "saas_a"}


# ── regression guards for the seam-detection fixes ─────────────────────────────
# Grounded in Helland, "Data on the Outside vs. Data on the Inside" (CIDR 2005):
# cross-boundary data is referenced by immutable key, never enforced by either DB,
# so a real key-reference seam must be detected — and an unrelated/blank connector
# must not silently swallow it.

def _blank_contract_map() -> SystemMap:
    """The full fixture but with the Order→Device connector's contract cleared."""
    data = generic_saas_abc_map().model_dump()
    data["connectors"][0]["contract"] = None
    return SystemMap.model_validate(data)


def test_blank_contract_connector_does_not_suppress_real_seam() -> None:
    # A connector that links the systems but names no field must NOT swallow the
    # distinct Order.device_id → Device seam (the `or not contract` suppression bug).
    seams = detect_cross_system_seams(_blank_contract_map())
    assert len(seams) == 1
    assert "device_id" in (seams[0].contract or "").lower()


def test_referenced_base_requires_separator_and_drops_identifier_words() -> None:
    # Real foreign-reference names parse; identifier-ish words do not.
    assert _referenced_base("device_id") == "device"
    assert _referenced_base("customer_ref") == "customer"
    assert _referenced_base("subject_ref") == "subject"
    for non_ref in ("uuid", "grid", "valid", "paid", "id", "status", "rapid"):
        assert _referenced_base(non_ref) is None, non_ref


def _evx() -> Evidence:
    return Evidence(id="ev_x", kind="manual", locator="manual://x", excerpt="x", confidence=0.9)


def _identifier_field_map() -> SystemMap:
    """Two systems: Widget (sys A) references Gizmo (sys B) via gizmo_id, and also
    carries identifier-like fields (uuid/grid/valid) that must NOT seam."""
    def sysm(sid, name, kind):
        return EnterpriseSystem(id=sid, name=name, kind=kind, evidence=[_evx()],
                                confidence=0.9, review_status="accepted")

    def surf(sid, system_id):
        return AccessSurface(id=sid, system_id=system_id, kind="openapi_endpoint",
                             operation="read", name="GET /x", address="https://x",
                             evidence=[_evx()], confidence=0.9, review_status="accepted")

    def obj(oid, system_id, name, surface_id):
        return DataObject(id=oid, system_id=system_id, surface_ids=[surface_id], name=name,
                          evidence=[_evx()], confidence=0.9, review_status="accepted")

    def fld(fid, object_id, name):
        return DataField(id=fid, object_id=object_id, name=name, type="string", nullable=True,
                         sensitivity="internal", source_path=f"$.{name}", evidence=[_evx()],
                         confidence=0.9, review_status="accepted")

    return SystemMap(
        systems=[sysm("sa", "System A", "mcp_server"), sysm("sb", "System B", "saas")],
        access_surfaces=[surf("surf_a", "sa"), surf("surf_b", "sb")],
        data_objects=[obj("o_widget", "sa", "Widget", "surf_a"),
                      obj("o_gizmo", "sb", "Gizmo", "surf_b")],
        data_fields=[
            fld("f_wpk", "o_widget", "widget_id"),   # self-reference → not a seam
            fld("f_gid", "o_widget", "gizmo_id"),     # → Gizmo in System B → the one seam
            fld("f_uuid", "o_widget", "uuid"),        # identifier-like → must not seam
            fld("f_grid", "o_widget", "grid"),
            fld("f_valid", "o_widget", "valid"),
            fld("f_gpk", "o_gizmo", "gizmo_id"),      # Gizmo's own key → not a seam
        ],
    )


def test_identifier_like_fields_do_not_produce_spurious_seams() -> None:
    seams = detect_cross_system_seams(_identifier_field_map())
    assert len(seams) == 1
    seam = seams[0]
    assert seam.from_system == "sa" and seam.to_systems == ["sb"]
    assert "gizmo_id" in (seam.contract or "").lower()
    joined = " ".join((s.contract or "") for s in seams).lower()
    for noise in ("uuid", "grid", "valid"):
        assert noise not in joined
