import { useEffect, useState } from "react";
import { API } from "../config/api";
import type { PenFile } from "../types/pen";
import { LandingPage } from "./LandingPage";
import { LogOut, Trash2, Plus } from "lucide-react";

type ProjectSummary = {
  id: string;
  name: string;
  role: "owner" | "editor";
  revision: number;
  updated_at: string;
  owner_id: string;
};

type Props = {
  username: string;
  onOpenProject: (id: string, pen: PenFile) => void;
  onLogout: () => void;
};

export function ProjectList({ username, onOpenProject, onLogout }: Props) {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [showLanding, setShowLanding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const res = await fetch(API.projectList());
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const data = await res.json();
      setProjects(data.projects);
    } catch (err: any) {
      setError(err.message || String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function openExisting(id: string) {
    try {
      const res = await fetch(API.projects(id));
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const pen: PenFile = await res.json();
      onOpenProject(id, pen);
    } catch (err: any) {
      alert(`Failed to open: ${err.message || err}`);
    }
  }

  async function deleteProject(id: string, name: string) {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(API.deleteProject(id), { method: "DELETE" });
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      refresh();
    } catch (err: any) {
      alert(`Failed to delete: ${err.message || err}`);
    }
  }

  async function logout() {
    await fetch(API.logout(), { method: "POST" }).catch(() => {});
    onLogout();
  }

  if (showLanding) {
    return (
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 pt-3">
          <button
            onClick={() => setShowLanding(false)}
            className="text-xs text-gray-500 hover:text-gray-700"
          >
            ← Back to your projects
          </button>
        </div>
        <LandingPage
          onIngested={onOpenProject}
          onStartBlank={onOpenProject}
          onLoadExample={onOpenProject}
          onLoadMorSat0Exercise={onOpenProject}
          onLoadClaudeEval={onOpenProject}
          onLoadRepoAnalysis={onOpenProject}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">DataRoot</h1>
          <p className="text-xs text-gray-500">Signed in as {username}</p>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700"
        >
          <LogOut className="w-3.5 h-3.5" />
          Log out
        </button>
      </header>

      <main className="max-w-4xl mx-auto p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">Your projects</h2>
          <button
            onClick={() => setShowLanding(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4" />
            New project
          </button>
        </div>

        {error && (
          <div className="mb-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}

        {projects === null ? (
          <div className="text-sm text-gray-500">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded p-6 text-center text-sm text-gray-500">
            No projects yet. Click "New project" to start.
          </div>
        ) : (
          <ul className="bg-white border border-gray-200 rounded divide-y divide-gray-200">
            {projects.map((p) => (
              <li key={p.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50">
                <button
                  onClick={() => openExisting(p.id)}
                  className="flex-1 text-left"
                >
                  <div className="text-sm font-medium text-gray-900">{p.name}</div>
                  <div className="text-xs text-gray-500">
                    {p.role === "owner" ? "Owner" : "Editor"} · revision {p.revision} · updated{" "}
                    {new Date(p.updated_at).toLocaleString()}
                  </div>
                </button>
                {p.role === "owner" && (
                  <button
                    onClick={() => deleteProject(p.id, p.name)}
                    className="ml-3 p-1.5 text-gray-400 hover:text-red-600"
                    title="Delete project"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
