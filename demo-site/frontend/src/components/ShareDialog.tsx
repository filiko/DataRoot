import { useState } from "react";
import { API } from "../config/api";
import { Share2, Copy, X } from "lucide-react";

type Props = {
  projectId: string;
  onClose: () => void;
};

export function ShareDialog({ projectId, onClose }: Props) {
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(API.createInvite(projectId), { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Failed (${res.status})`);
      }
      const data = await res.json();
      const url = `${window.location.origin}/invite/${data.token}`;
      setLink(url);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-lg border border-gray-200 w-full max-w-md p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Share2 className="w-4 h-4 text-indigo-600" />
            <h2 className="text-base font-semibold text-gray-900">Share this project</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-gray-500 mb-3">
          Generate an invite link. Anyone signed in to DataRoot who opens it will be added as an editor.
          Link expires in 7 days or after 20 uses.
        </p>

        {!link ? (
          <button
            onClick={generate}
            disabled={busy}
            className="w-full py-1.5 rounded bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
          >
            {busy ? "Generating…" : "Generate invite link"}
          </button>
        ) : (
          <div className="space-y-2">
            <div className="flex gap-1">
              <input
                readOnly
                value={link}
                className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-xs font-mono bg-gray-50"
                onFocus={(e) => e.currentTarget.select()}
              />
              <button
                onClick={copy}
                className="px-2 py-1.5 rounded bg-gray-100 hover:bg-gray-200 text-xs flex items-center gap-1"
              >
                <Copy className="w-3.5 h-3.5" />
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Send this to your collaborator. They must sign up or log in first.
            </p>
          </div>
        )}

        {error && (
          <div className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
