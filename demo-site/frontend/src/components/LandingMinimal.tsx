import React, { useCallback, useRef, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import type { PenFile } from "../types/pen";
import { API as API_ROUTES } from "../config/api";
import {
  DEFAULT_REPO_PATH,
  LOCAL_ANALYZE_BASH,
  LOCAL_ANALYZE_OUTPUT,
  LOCAL_ANALYZE_POWERSHELL,
  SERVER_REPO_ANALYSIS_ENABLED,
  analyzeRepository,
  analyzeRepositoryFolder,
  folderNameFromFiles,
  importDfdJsonFile,
  repoNameFromPath,
} from "./repoAnalysis";

const REPO_ANALYSIS_STEPS = [
  "Indexing repository files…",
  "Parsing Python with ast…",
  "Parsing TypeScript with regex…",
  "Building call graph…",
  "Inferring entities from Pydantic models…",
  "Inferring DFD processes from FastAPI routes…",
  "Composing PenFile…",
];

const FEATURES = [
  { num: "01", title: "Repo analysis",             body: "Point it at any Python or TypeScript codebase. DataRoot parses ASTs, infers entities, maps call graphs, and builds both diagrams automatically.", aside: "Python · TypeScript · FastAPI · Pydantic" },
  { num: "02", title: "ERD + DFD in one pass",     body: "Every source produces both an Entity Relationship Diagram and a multi-level Data Flow Diagram. Drill into process-level sub-diagrams with a click.", aside: "Entities · Relations · Processes · Flows" },
  { num: "03", title: "Interactive canvas",         body: "Drag nodes, reconnect edges, rename labels. Hit Auto Arrange and the solver places everything optimally. Changes persist in .dfd.json.", aside: "React Flow · Auto-layout · Drag & drop" },
  { num: "04", title: "Export anywhere",            body: "DBML, Mermaid, SQL CREATE statements, or the native .dfd.json format. Round-trip safely — import and pick up exactly where you left off.", aside: "DBML · Mermaid · SQL · JSON" },
  { num: "05", title: "Collaborate with your team", body: "Commit .dfd.json alongside your schema migrations. Everyone on the team sees the same diagrams, always in sync with the codebase.", aside: ".dfd.json · Git · Version control" },
  { num: "06", title: "Modular styling",            body: "Switch the entire interface between themes — chalkboard, minimal, and more. Pick the one that fits how you think.", aside: "Chalkboard · Minimal · Themes" },
];

interface Props {
  onIngested: (projectId: string, pen: PenFile) => void;
  onStartBlank: (projectId: string, pen: PenFile) => void;
  onLoadExample: (projectId: string, pen: PenFile) => void;
  onLoadNexusExercise: (projectId: string, pen: PenFile) => void;
  onLoadClaudeEval: (projectId: string, pen: PenFile) => void;
  onLoadRepoAnalysis: (projectId: string, pen: PenFile) => void;
}

export function LandingMinimal({
  onIngested, onStartBlank, onLoadExample, onLoadNexusExercise, onLoadClaudeEval, onLoadRepoAnalysis,
}: Props) {
  const [dragging,     setDragging]     = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState<string | null>(null);
  const [repoAnalyzing,setRepoAnalyzing]= useState(false);
  const [repoStep,     setRepoStep]     = useState(0);
  const [repoPicking,  setRepoPicking]  = useState(false);
  const [repoPath,     setRepoPath]     = useState(DEFAULT_REPO_PATH);
  const [activeRepoPath, setActiveRepoPath] = useState(DEFAULT_REPO_PATH);
  const repoFolderRef = useRef<HTMLInputElement>(null);
  const openFileRef = useRef<HTMLInputElement>(null);
  const startRef    = useRef<HTMLDivElement>(null);

  const upload = useCallback(async (files: File[]) => {
    if (!files.length) return;
    setLoading(true); setError(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const res = await fetch(`${API_ROUTES.ingest()}?project_name=${encodeURIComponent(files[0].name.replace(/\.[^.]+$/, ""))}`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      const d = await res.json();
      onIngested(d.project_id, d.pen);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Upload failed"); }
    finally { setLoading(false); }
  }, [onIngested]);

  const apiCall = useCallback(async (url: string, cb: (d: { project_id: string; pen: PenFile }) => void) => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      cb(await res.json());
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setLoading(false); }
  }, []);

  const handleAnalyzeRepo = useCallback(async () => {
    const targetPath = repoPath.trim();
    if (!targetPath) {
      setError("Repository path is required");
      return;
    }
    setActiveRepoPath(targetPath);
    setError(null); setRepoAnalyzing(true); setRepoStep(0);
    const iv = window.setInterval(() => setRepoStep((p) => Math.min(p + 1, REPO_ANALYSIS_STEPS.length - 1)), 450);
    try {
      const [d] = await Promise.all([
        analyzeRepository(targetPath),
        new Promise((r) => window.setTimeout(r, REPO_ANALYSIS_STEPS.length * 450 + 200)),
      ]);
      window.clearInterval(iv);
      setRepoStep(REPO_ANALYSIS_STEPS.length);
      await new Promise((r) => window.setTimeout(r, 400));
      onLoadRepoAnalysis(d.project_id, d.pen);
    } catch (e: unknown) { window.clearInterval(iv); setError(e instanceof Error ? e.message : "Repo analysis failed"); }
    finally { setRepoAnalyzing(false); }
  }, [onLoadRepoAnalysis, repoPath]);

  const handleAnalyzeRepoFolder = useCallback(async (files: FileList | null) => {
    if (!files?.length) return;
    const folderName = folderNameFromFiles(files);
    setActiveRepoPath(folderName);
    setError(null); setRepoAnalyzing(true); setRepoStep(0);
    const iv = window.setInterval(() => setRepoStep((p) => Math.min(p + 1, REPO_ANALYSIS_STEPS.length - 1)), 450);
    try {
      const [d] = await Promise.all([
        analyzeRepositoryFolder(files),
        new Promise((r) => window.setTimeout(r, REPO_ANALYSIS_STEPS.length * 450 + 200)),
      ]);
      window.clearInterval(iv);
      setRepoStep(REPO_ANALYSIS_STEPS.length);
      await new Promise((r) => window.setTimeout(r, 400));
      onLoadRepoAnalysis(d.project_id, d.pen);
    } catch (e: unknown) { window.clearInterval(iv); setError(e instanceof Error ? e.message : "Repo analysis failed"); }
    finally {
      setRepoAnalyzing(false);
      if (repoFolderRef.current) repoFolderRef.current.value = "";
    }
  }, [onLoadRepoAnalysis]);

  const handleOpenDfd = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setLoading(true); setError(null);
    try {
      const d = await importDfdJsonFile(file);
      onIngested(d.project_id, d.pen);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed to open file"); }
    finally { setLoading(false); if (openFileRef.current) openFileRef.current.value = ""; }
  }, [onIngested]);

  return (
    <div className="bg-white min-h-full overflow-y-auto" style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* ── Hero ── */}
      <section className="bg-[#0a0a0a] text-white">
        <div className="border-b border-white/10 px-8 py-4 flex items-center justify-between">
          <span className="text-sm font-semibold tracking-tight">DataRoot</span>
          <div className="flex items-center gap-4">
            <button onClick={() => apiCall(API_ROUTES.example(), (d) => onLoadExample(d.project_id, d.pen))} disabled={loading} className="text-sm text-white/50 hover:text-white transition-colors disabled:opacity-40">Demo</button>
            <a href="/docs" className="text-sm text-white/50 hover:text-white transition-colors">Docs</a>
          </div>
        </div>

        <div className="px-8 pt-20 pb-24 max-w-5xl mx-auto">
          <div className="text-xs text-white/40 tracking-[0.18em] uppercase mb-8 font-mono">
            data architecture tooling
          </div>
          <h1 className="font-black text-white leading-[0.95] tracking-tight mb-10" style={{ fontSize: "clamp(56px, 9vw, 108px)" }}>
            Your schema,<br />
            <span className="text-white/30">mapped.</span>
          </h1>
          <div className="flex flex-col sm:flex-row gap-8 sm:items-end sm:justify-between max-w-3xl">
            <p className="text-white/55 text-lg leading-relaxed max-w-sm">
              Upload a spreadsheet or point at a codebase. DataRoot generates ERD and DFD diagrams — you arrange and export.
            </p>
            <div className="flex gap-3 flex-shrink-0">
              <button onClick={() => startRef.current?.scrollIntoView({ behavior: "smooth" })} className="bg-white text-black text-sm font-semibold px-6 py-3 hover:bg-white/90 transition-colors">
                Open app
              </button>
              <button onClick={() => apiCall(API_ROUTES.example(), (d) => onLoadExample(d.project_id, d.pen))} disabled={loading} className="border border-white/20 text-white text-sm px-6 py-3 hover:border-white/50 transition-colors disabled:opacity-40">
                Try example
              </button>
            </div>
          </div>
        </div>

        <div className="border-t border-white/10 px-8 py-4 flex gap-8 text-xs text-white/25 font-mono tracking-widest">
          <span>ERD</span><span>DFD</span><span>DBML</span><span>MERMAID</span><span>SQL</span>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-8">
          {FEATURES.map((f, i) => (
            <div key={f.num} className={`grid grid-cols-[72px_1fr_auto] gap-10 py-11 ${i < FEATURES.length - 1 ? "border-b border-gray-200" : ""} items-start`}>
              <div className="text-xs text-gray-400 font-mono pt-1 tabular-nums">{f.num}</div>
              <div>
                <div className="text-lg font-semibold text-gray-900 mb-3">{f.title}</div>
                <div className="text-base text-gray-500 leading-relaxed max-w-xl">{f.body}</div>
              </div>
              <div className="text-[11px] text-gray-500 font-mono text-right leading-loose hidden sm:block pt-1">
                {f.aside.split(" · ").map((t) => <div key={t}>{t}</div>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Get Started ── */}
      <section ref={startRef} className="max-w-2xl mx-auto px-8 py-20">
        <div className="text-xs text-gray-400 font-mono tracking-[0.16em] uppercase mb-10">
          get started
        </div>

        {/* Repo card */}
        <div className="border border-gray-200 mb-4">
          <button
            onClick={() => setRepoPicking((v) => !v)}
            disabled={loading || repoAnalyzing}
            className="w-full flex items-center gap-4 px-5 py-5 text-left hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <span className="text-sm font-mono text-gray-300 w-6 text-center">⊞</span>
            <span className="flex-1">
              <span className="block text-base font-semibold text-gray-900">Analyze a repository locally</span>
              <span className="block text-sm text-gray-400 mt-1">Generate one .dfd.json file, then import it here</span>
            </span>
            <span className="text-[10px] font-mono tracking-widest uppercase text-gray-300 border border-gray-200 px-2 py-0.5">local</span>
            <span className={`text-gray-400 text-base transition-transform ${repoPicking ? "rotate-90" : ""}`}>›</span>
          </button>

          {repoPicking && (
            <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
              <button
                type="button"
                onClick={() => openFileRef.current?.click()}
                className="w-full py-3 bg-gray-900 text-white text-sm font-semibold hover:bg-black transition-colors"
              >
                Import generated .dfd.json
              </button>
              <div className="mt-3 border border-gray-200 bg-white p-3">
                <div className="text-[11px] text-gray-400 uppercase tracking-wider font-semibold mb-2">Generate locally</div>
                <pre className="whitespace-pre-wrap break-all bg-gray-950 px-3 py-2 text-[11px] leading-5 text-gray-100">{LOCAL_ANALYZE_POWERSHELL}</pre>
                <pre className="mt-2 whitespace-pre-wrap break-all bg-gray-950 px-3 py-2 text-[11px] leading-5 text-gray-100">{LOCAL_ANALYZE_BASH}</pre>
                <div className="mt-2 text-xs text-gray-400">
                  Output: <span className="font-mono">{LOCAL_ANALYZE_OUTPUT}</span>
                </div>
              </div>
              {SERVER_REPO_ANALYSIS_ENABLED && (
                <>
                  <div className="flex items-center gap-3 my-4">
                    <div className="flex-1 border-t border-gray-200" />
                    <span className="text-xs text-gray-400 font-mono">local backend</span>
                    <div className="flex-1 border-t border-gray-200" />
                  </div>
                  <label className="block text-[11px] text-gray-400 uppercase tracking-wider font-semibold mb-2">
                    Repository path
                  </label>
                  <input
                    value={repoPath}
                    onChange={(event) => setRepoPath(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        setRepoPicking(false);
                        handleAnalyzeRepo();
                      }
                    }}
                    placeholder="C:\Users\name\Documents\Github\repo"
                    className="w-full border border-gray-200 bg-white px-3 py-2.5 text-sm font-mono text-gray-800 outline-none focus:border-gray-900"
                  />
                  <button onClick={() => { setRepoPicking(false); handleAnalyzeRepo(); }} disabled={!repoPath.trim()}
                    className="mt-3 w-full py-3 border border-gray-300 bg-white text-gray-800 text-sm font-semibold hover:border-gray-900 transition-colors disabled:opacity-40"
                  >
                    Analyze {repoNameFromPath(repoPath)}
                  </button>
                  <button
                    type="button"
                    onClick={() => repoFolderRef.current?.click()}
                    className="mt-2 w-full py-3 border border-gray-300 bg-white text-gray-800 text-sm font-semibold hover:border-gray-900 transition-colors"
                  >
                    Upload selected repository folder
                  </button>
                </>
              )}
              <input
                ref={repoFolderRef}
                type="file"
                multiple
                className="hidden"
                onChange={(event) => {
                  setRepoPicking(false);
                  handleAnalyzeRepoFolder(event.target.files);
                }}
                {...{ webkitdirectory: "", directory: "" }}
              />
            </div>
          )}
        </div>

        {/* Drop zone */}
        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); upload(Array.from(e.dataTransfer.files).filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name))); }}
          className={`block border-2 border-dashed px-8 py-16 text-center cursor-pointer transition-colors mb-5 ${dragging ? "border-gray-900 bg-gray-50" : "border-gray-200 hover:border-gray-400"}`}
        >
          <input type="file" accept=".xlsx,.xls,.csv" multiple className="hidden" onChange={(e) => upload(Array.from(e.target.files || []))} />
          {loading ? (
            <div className="flex flex-col items-center gap-3 text-gray-400">
              <Loader2 size={28} className="animate-spin" />
              <span className="text-base">Parsing spreadsheet…</span>
            </div>
          ) : (
            <div>
              <div className="text-3xl text-gray-200 mb-4">↑</div>
              <div className="text-base font-semibold text-gray-700 mb-2">Drop files here</div>
              <div className="text-sm text-gray-400 mb-5">or click to browse</div>
              <div className="flex gap-2 justify-center">
                {[".xlsx", ".xls", ".csv"].map((ext) => (
                  <span key={ext} className="border border-gray-200 px-2.5 py-1 text-xs font-mono text-gray-400">{ext}</span>
                ))}
              </div>
            </div>
          )}
        </label>

        {/* Divider */}
        <div className="flex items-center gap-4 mb-5">
          <div className="flex-1 border-t border-gray-200" />
          <span className="text-sm text-gray-400 font-mono">or</span>
          <div className="flex-1 border-t border-gray-200" />
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 justify-center">
          <button
            onClick={() => openFileRef.current?.click()}
            disabled={loading}
            className="text-sm border border-gray-200 px-4 py-2 text-gray-600 hover:border-gray-900 hover:text-gray-900 transition-colors disabled:opacity-40 font-mono"
          >
            Open .dfd.json
          </button>
          {[
            { label: "Load example",   action: () => apiCall(API_ROUTES.example(),       (d) => onLoadExample(d.project_id, d.pen)) },
            { label: "Nexus — Codex",  action: () => apiCall(API_ROUTES.nexusExercise(), (d) => onLoadNexusExercise(d.project_id, d.pen)) },
            { label: "Nexus — Claude", action: () => apiCall(API_ROUTES.claudeEval(),    (d) => onLoadClaudeEval(d.project_id, d.pen)) },
            { label: "Blank canvas",   action: () => apiCall(API_ROUTES.blank(),         (d) => onStartBlank(d.project_id, d.pen)) },
          ].map((b) => (
            <button key={b.label} onClick={b.action} disabled={loading}
              className="text-sm border border-gray-200 px-4 py-2 text-gray-600 hover:border-gray-900 hover:text-gray-900 transition-colors disabled:opacity-40 font-mono"
            >
              {b.label}
            </button>
          ))}
          <input ref={openFileRef} type="file" accept=".dfd.json,.json" className="hidden" onChange={handleOpenDfd} />
        </div>

        {error && (
          <div className="mt-5 border border-red-200 bg-red-50 px-4 py-3 text-red-600 text-sm">
            {error}
          </div>
        )}
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-200 px-8 py-6 flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-900">DataRoot</span>
        <span className="text-xs text-gray-500 font-mono">FastAPI · React · React Flow</span>
      </footer>

      {/* ── Repo analysis overlay ── */}
      {repoAnalyzing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center">
          <div className="w-full max-w-md bg-white border border-gray-200 p-8">
            <div className="text-base font-semibold text-gray-900 mb-1">Analyzing repository</div>
            <div className="text-xs text-gray-400 font-mono mb-6 break-all">{activeRepoPath}</div>
            <ol className="flex flex-col gap-3">
              {REPO_ANALYSIS_STEPS.map((step, idx) => {
                const done = idx < repoStep, active = idx === repoStep;
                return (
                  <li key={step} className={`flex items-center gap-3 transition-opacity ${done || active ? "opacity-100" : "opacity-30"}`}>
                    <span className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                      {done ? <Check size={13} className="text-gray-900" /> : active ? <Loader2 size={13} className="text-gray-600 animate-spin" /> : <span className="w-1.5 h-1.5 rounded-full bg-gray-300 block" />}
                    </span>
                    <span className={`text-sm font-mono ${active ? "text-gray-900 font-semibold" : "text-gray-500"} ${done ? "line-through text-gray-400" : ""}`}>
                      {step}
                    </span>
                  </li>
                );
              })}
            </ol>
            <div className="mt-6 text-xs text-gray-400 italic">Generating diagrams from repository source.</div>
          </div>
        </div>
      )}
    </div>
  );
}
