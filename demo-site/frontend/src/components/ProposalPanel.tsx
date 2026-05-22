import React, { useState } from "react";
import { AlertTriangle, CheckCircle, XCircle, HelpCircle } from "lucide-react";
import type { ReviewProposal, PenFile, WarningEntry } from "../types/pen";

import { API_BASE as API } from "../config/api";

interface Props {
  projectId: string;
  pen: PenFile;
  onUpdate: (pen: PenFile) => void;
}

const PROPOSAL_ICONS: Record<string, string> = {
  entity_split: "🗂",
  foreign_key: "🔗",
  enum_to_lookup: "📋",
  add_column_from_dfd: "➕",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-orange-100 text-orange-800",
};

function confidenceLabel(c: number): { label: string; key: string } {
  if (c >= 0.85) return { label: `${Math.round(c * 100)}% confident`, key: "high" };
  if (c >= 0.65) return { label: `${Math.round(c * 100)}% confident`, key: "medium" };
  return { label: `${Math.round(c * 100)}% confident`, key: "low" };
}

async function applyProposal(projectId: string, proposalId: string, answerIndex: number): Promise<PenFile> {
  const res = await fetch(`${API}/schema/${projectId}/apply-proposal`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proposal_id: proposalId, answer_index: answerIndex }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function savePen(projectId: string, pen: PenFile): Promise<PenFile> {
  const res = await fetch(`${API}/schema/${projectId}/pen`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pen),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

interface CardProps {
  proposal: ReviewProposal;
  projectId: string;
  onAnswered: (pen: PenFile) => void;
}

function ProposalCard({ proposal, projectId, onAnswered }: CardProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const icon = PROPOSAL_ICONS[proposal.proposal_type] || "📌";
  const { label: confLabel, key: confKey } = confidenceLabel(proposal.confidence);

  const answer = async (idx: number) => {
    setLoading(true);
    setError(null);
    try {
      const pen = await applyProposal(projectId, proposal.id, idx);
      onAnswered(pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to apply");
    } finally {
      setLoading(false);
    }
  };

  const statusIcons: Record<string, React.ReactNode> = {
    pending: null,
    accepted: <CheckCircle className="w-5 h-5 text-green-600" />,
    rejected: <XCircle className="w-5 h-5 text-red-400" />,
  };

  if (proposal.status !== "pending") {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-500">
        <span className="flex items-center gap-2">
          {statusIcons[proposal.status]}
          <span className="text-gray-400 line-through">{proposal.title}</span>
        </span>
        <span className="text-xs capitalize text-gray-400">{proposal.status}</span>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl" role="img">{icon}</span>
          <span className="font-semibold text-gray-900 text-sm">{proposal.title}</span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_COLORS[confKey]}`}>
          {confLabel}
        </span>
      </div>

      <p className="text-sm text-gray-600 mb-4 leading-relaxed">{proposal.question}</p>

      {proposal.source_evidence.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1">
          {proposal.source_evidence.map((src) => (
            <span key={src} className="text-xs bg-blue-50 text-blue-700 rounded px-2 py-0.5 font-mono">
              {src}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2">
        {proposal.options.map((opt, idx) => {
          const isAccept = idx === 0;
          const isReject = idx === 1;
          return (
            <button
              key={idx}
              disabled={loading}
              onClick={() => answer(idx)}
              className={`
                flex items-center gap-2 text-left px-4 py-2.5 rounded-lg text-sm font-medium
                transition-colors duration-100 disabled:opacity-50
                ${isAccept
                  ? "bg-blue-600 text-white hover:bg-blue-700"
                  : isReject
                    ? "bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
                    : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                }
              `}
            >
              {isAccept && <CheckCircle className="w-4 h-4 flex-shrink-0" />}
              {isReject && <XCircle className="w-4 h-4 flex-shrink-0" />}
              {!isAccept && !isReject && <HelpCircle className="w-4 h-4 flex-shrink-0" />}
              <span>{opt}</span>
            </button>
          );
        })}
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}

function warningKey(warning: WarningEntry): string {
  return `${warning.rule_id}:${warning.node_kind}:${warning.node_id || warning.node_name || warning.message}`;
}

function clonePen(pen: PenFile): PenFile {
  return JSON.parse(JSON.stringify(pen)) as PenFile;
}

interface WarningProposal {
  id: string;
  title: string;
  change: string;
  warningText: string;
  warnings: WarningEntry[];
  apply: (pen: PenFile) => PenFile;
}

function buildWarningProposals(pen: PenFile): WarningProposal[] {
  const proposals: WarningProposal[] = [];

  for (const warning of pen.review.warnings.filter((w) => w.rule_id === "ERD-01")) {
    if (!warning.node_id) continue;
    proposals.push({
      id: `warning-${warningKey(warning)}`,
      title: `Proposal: Change "${warning.node_name || "entity"}" to rejected`,
      change: "Mark the orphan entity as rejected so it stops generating diagram warnings.",
      warningText: warning.message,
      warnings: [warning],
      apply: (current) => {
        const next = clonePen(current);
        const entity = next.erd.entities.find((item) => item.id === warning.node_id);
        if (entity) entity.review_status = "rejected";
        return next;
      },
    });
  }

  const groupedStoreWarnings = [
    {
      ruleId: "DFD-10",
      title: "Proposal: Change read-only data stores to accepted source stores",
      change: "Treat these as intentional reference/source stores and hide this warning group.",
    },
    {
      ruleId: "DFD-11",
      title: "Proposal: Change write-only data stores to accepted sink stores",
      change: "Treat these as intentional output/archive stores and hide this warning group.",
    },
  ];

  for (const group of groupedStoreWarnings) {
    const warnings = pen.review.warnings.filter((w) => w.rule_id === group.ruleId);
    if (warnings.length === 0) continue;
    const names = warnings.map((w) => w.node_name || "Unnamed store").join(", ");
    proposals.push({
      id: `warning-group-${group.ruleId}`,
      title: group.title,
      change: group.change,
      warningText: `${warnings.length} ${warnings.length === 1 ? "store" : "stores"}: ${names}`,
      warnings,
      apply: (current) => {
        const next = clonePen(current);
        const existing = new Set(next.review.dismissed_warnings || []);
        warnings.forEach((warning) => existing.add(warningKey(warning)));
        next.review.dismissed_warnings = Array.from(existing);
        return next;
      },
    });
  }

  return proposals;
}

export function countWarningProposals(pen: PenFile): number {
  return buildWarningProposals(pen).length;
}

function WarningProposalCard({
  proposal,
  projectId,
  pen,
  onAnswered,
}: {
  proposal: WarningProposal;
  projectId: string;
  pen: PenFile;
  onAnswered: (pen: PenFile) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const accept = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await savePen(projectId, proposal.apply(pen));
      onAnswered(updated);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to apply");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white border border-amber-200 rounded-xl p-5 shadow-sm">
      <div className="flex items-start gap-3 mb-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="min-w-0">
          <div className="font-semibold text-gray-900 text-sm">{proposal.title}</div>
          <p className="text-sm text-gray-600 mt-1 leading-relaxed">{proposal.change}</p>
        </div>
      </div>

      <div className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-900 mb-4">
        <span className="font-semibold">Warning: </span>
        {proposal.warningText}
      </div>

      <button
        disabled={loading}
        onClick={accept}
        className="flex w-full items-center gap-2 text-left px-4 py-2.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
      >
        <CheckCircle className="w-4 h-4 flex-shrink-0" />
        <span>{loading ? "Applying..." : "Approve change"}</span>
      </button>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

export function ProposalPanel({ projectId, pen, onUpdate }: Props) {
  const pending = pen.review.proposals.filter((p) => p.status === "pending");
  const done = pen.review.proposals.filter((p) => p.status !== "pending");
  const warningProposals = buildWarningProposals(pen);
  const totalPending = pending.length + warningProposals.length;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">Review Proposals</h2>
        <span className="text-xs text-gray-500 bg-gray-100 rounded-full px-2 py-0.5">
          {totalPending} pending
        </span>
      </div>

      {totalPending === 0 && done.length === 0 && (
        <div className="text-center text-sm text-gray-400 py-12">
          No proposals yet. Upload a spreadsheet to get started.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {warningProposals.map((p) => (
          <WarningProposalCard
            key={p.id}
            proposal={p}
            projectId={projectId}
            pen={pen}
            onAnswered={onUpdate}
          />
        ))}
        {pending.map((p) => (
          <ProposalCard key={p.id} proposal={p} projectId={projectId} onAnswered={onUpdate} />
        ))}
        {done.length > 0 && (
          <>
            <div className="text-xs text-gray-400 uppercase tracking-wide mt-2 mb-1">Reviewed</div>
            {done.map((p) => (
              <ProposalCard key={p.id} proposal={p} projectId={projectId} onAnswered={onUpdate} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
