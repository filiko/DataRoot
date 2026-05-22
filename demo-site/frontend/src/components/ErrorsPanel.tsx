import { useEffect, useState } from "react";
import { AlertTriangle, AlertCircle } from "lucide-react";
import type { AnalyzeResponse, PenFile } from "../types/pen";

const API = "";

interface Props {
  projectId: string;
  pen: PenFile;
}

interface IssueItem {
  id: string;
  severity: "error" | "warning";
  message: string;
  type: string;
  object_id: string;
  object_type: string;
  fix_suggestion: string | null;
}

export function ErrorsPanel({ projectId, pen }: Props) {
  const [issues, setIssues] = useState<IssueItem[]>([]);
  const [loading, setLoading] = useState(false);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    fetch(`${API}/schema/${projectId}/analyze`)
      .then((r) => r.json())
      .then((data: AnalyzeResponse) => {
        const items: IssueItem[] = [];

        for (const c of data.conflicts) {
          items.push({
            id: `conflict-${c.object_id}-${c.type}`,
            severity: c.severity === "blocking" ? "error" : "warning",
            message: c.message,
            type: c.type,
            object_id: c.object_id,
            object_type: "conflict",
            fix_suggestion: null,
          });
        }

        for (const i of data.static_issues) {
          items.push({
            id: `static-${i.object_id}-${i.category}`,
            severity: i.severity,
            message: i.message,
            type: i.category,
            object_id: i.object_id,
            object_type: i.object_type,
            fix_suggestion: i.fix_suggestion,
          });
        }

        setIssues(items);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [projectId, pen]);
  /* eslint-enable react-hooks/set-state-in-effect */

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Analyzing diagram...
      </div>
    );
  }

  if (issues.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-4">
        <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mb-3">
          <span className="text-2xl">✅</span>
        </div>
        <p className="text-sm font-medium text-gray-700 mb-1">No issues found</p>
        <p className="text-xs text-gray-400">Your diagram passes validation and static analysis.</p>
      </div>
    );
  }

  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  return (
    <div className="h-full overflow-y-auto p-4">
      {errors.length > 0 && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <h2 className="font-semibold text-gray-900 text-sm">Blocking Issues ({errors.length})</h2>
          </div>
          <div className="flex flex-col gap-2 mb-6">
            {errors.map((issue) => (
              <IssueCard key={issue.id} issue={issue} />
            ))}
          </div>
        </>
      )}

      {warnings.length > 0 && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            <h2 className="font-semibold text-gray-900 text-sm">Warnings ({warnings.length})</h2>
          </div>
          <div className="flex flex-col gap-2">
            {warnings.map((issue) => (
              <IssueCard key={issue.id} issue={issue} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function IssueCard({ issue }: { issue: IssueItem }) {
  const isError = issue.severity === "error";

  return (
    <div
      className={`
        border rounded-lg p-4 text-sm
        ${isError
          ? "bg-red-50 border-red-200"
          : "bg-yellow-50 border-yellow-200"
        }
      `}
    >
      <div className="flex items-start gap-2">
        <div className="mt-0.5">
          {isError
            ? <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
            : <AlertTriangle className="w-4 h-4 text-yellow-500 flex-shrink-0" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <p className={`font-medium ${isError ? "text-red-800" : "text-yellow-800"}`}>
            {issue.message}
          </p>
          <p className={`text-xs mt-1 ${isError ? "text-red-600" : "text-yellow-700"}`}>
            {issue.object_type} · {issue.type}
          </p>
          {issue.fix_suggestion && (
            <p className={`text-xs mt-1 ${isError ? "text-red-600" : "text-yellow-700"}`}>
              💡 {issue.fix_suggestion}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
