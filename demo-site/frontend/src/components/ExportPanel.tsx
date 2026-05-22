import { useState } from "react";
import { Download, Copy, Check, Loader2 } from "lucide-react";

import { API_BASE as API } from "../config/api";

type ExportFormat = "sql" | "mermaid" | "dbml" | "pen";

interface Props {
  projectId: string;
}

const TABS: { id: ExportFormat; label: string; hint: string }[] = [
  { id: "sql", label: "PostgreSQL SQL", hint: "CREATE TABLE statements, FK constraints" },
  { id: "mermaid", label: "Mermaid ERD", hint: "Paste into any Mermaid viewer" },
  { id: "dbml", label: "DBML", hint: "Paste into dbdiagram.io" },
  { id: "pen", label: ".pen JSON", hint: "Full project file" },
];

export function ExportPanel({ projectId }: Props) {
  const [active, setActive] = useState<ExportFormat>("sql");
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (format: ExportFormat) => {
    setActive(format);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/schema/${projectId}/export/${format}`);
      if (!res.ok) throw new Error(await res.text());
      setContent(await res.text());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Export failed");
      setContent(null);
    } finally {
      setLoading(false);
    }
  };

  const handleTab = (format: ExportFormat) => {
    if (format !== active || content === null) {
      load(format);
    }
  };

  const copy = async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const download = () => {
    if (!content) return;
    const ext = active === "sql" ? "sql" : active === "pen" ? "pen.json" : active === "mermaid" ? "mmd" : "dbml";
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `schema.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Tabs */}
      <div className="flex border-b border-gray-200 bg-white">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTab(tab.id)}
            className={`
              px-4 py-3 text-sm font-medium transition-colors
              ${active === tab.id
                ? "border-b-2 border-blue-600 text-blue-600"
                : "text-gray-500 hover:text-gray-700"
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      {content && (
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
          <span className="text-xs text-gray-500">
            {TABS.find((t) => t.id === active)?.hint}
          </span>
          <div className="flex gap-2">
            <button
              onClick={copy}
              className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-200 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button
              onClick={download}
              className="flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 px-2 py-1 rounded hover:bg-gray-200 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              Download
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto bg-gray-900 p-0">
        {loading && (
          <div className="flex items-center justify-center h-full gap-2 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Generating export…</span>
          </div>
        )}
        {error && (
          <div className="m-4 p-3 bg-red-900/30 border border-red-700 rounded text-red-300 text-sm">
            {error}
          </div>
        )}
        {!loading && !error && content === null && (
          <div className="flex items-center justify-center h-full text-sm text-gray-500">
            Select a tab to generate the export
          </div>
        )}
        {!loading && content && (
          <pre className="text-sm font-mono text-green-300 p-4 leading-relaxed whitespace-pre overflow-x-auto">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}
