import React, { useState, useEffect } from "react";
import { AlertCircle, MessageSquare, List, Search } from "lucide-react";
import { ProposalPanel, countWarningProposals } from "./ProposalPanel";
import { ErrorsPanel } from "./ErrorsPanel";
import { ChatPanel } from "./ChatPanel";
import { AskPanel } from "./datademo/AskPanel";
import type { PenFile, AnalyzeResponse } from "../types/pen";

import { API_BASE as API } from "../config/api";

type SidebarTab = "ask" | "proposals" | "errors" | "chat";

interface Props {
  projectId: string;
  pen: PenFile;
  onPenUpdate: (pen: PenFile) => void;
}

export function SidebarGrading({ projectId, pen, onPenUpdate }: Props) {
  const [activeTab, setActiveTab] = useState<SidebarTab>("ask");
  const [issueCount, setIssueCount] = useState(0);

  useEffect(() => {
    if (!projectId) return;
    fetch(`${API}/schema/${projectId}/analyze`)
      .then((r) => r.json())
      .then((data: AnalyzeResponse) => {
        const blocking = data.conflicts.filter(
          (c: { severity: string }) => c.severity === "blocking"
        ).length;
        const staticErrors = data.static_issues.filter(
          (i: { severity: string }) => i.severity === "error"
        ).length;
        setIssueCount(blocking + staticErrors);
      })
      .catch(() => {});
  }, [projectId, pen]);

  const showErrorsTab = issueCount > 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-gray-200 bg-white px-2 pt-2">
        <TabButton
          active={activeTab === "ask"}
          onClick={() => setActiveTab("ask")}
          icon={<Search className="w-3.5 h-3.5" />}
          label="Ask"
        />
        <TabButton
          active={activeTab === "proposals"}
          onClick={() => setActiveTab("proposals")}
          icon={<List className="w-3.5 h-3.5" />}
          label="Proposals"
          badge={
            pen.review.proposals.filter((p) => p.status === "pending").length
            + countWarningProposals(pen)
          }
        />
        {showErrorsTab && (
          <TabButton
            active={activeTab === "errors"}
            onClick={() => setActiveTab("errors")}
            icon={<AlertCircle className="w-3.5 h-3.5" />}
            label="Errors"
            badge={issueCount}
            badgeColor="bg-red-100 text-red-700"
          />
        )}
        <TabButton
          active={activeTab === "chat"}
          onClick={() => setActiveTab("chat")}
          icon={<MessageSquare className="w-3.5 h-3.5" />}
          label="Chat"
        />
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === "ask" && <AskPanel />}
        {activeTab === "proposals" && (
          <ProposalPanel
            projectId={projectId}
            pen={pen}
            onUpdate={onPenUpdate}
          />
        )}
        {activeTab === "errors" && (
          <ErrorsPanel projectId={projectId} pen={pen} />
        )}
        {activeTab === "chat" && (
          <ChatPanel
            projectId={projectId}
            pen={pen}
            onApplySuggestion={(op, payload) => {
              console.log("Apply suggestion:", op, payload);
            }}
          />
        )}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
  badge,
  badgeColor = "bg-gray-100 text-gray-600",
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  badge?: number;
  badgeColor?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-1.5 px-3 pb-2 text-sm font-medium border-b-2 transition-colors
        ${
          active
            ? "border-indigo-600 text-indigo-700"
            : "border-transparent text-gray-500 hover:text-gray-700"
        }
      `}
    >
      {icon}
      {label}
      {badge !== undefined && badge > 0 && (
        <span className={`text-xs rounded-full px-1.5 py-0.5 ${badgeColor}`}>
          {badge}
        </span>
      )}
    </button>
  );
}
