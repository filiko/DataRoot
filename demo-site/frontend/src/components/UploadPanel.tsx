import React, { useCallback, useRef, useState } from "react";
import { Boxes, BrainCircuit, Upload, FileSpreadsheet, FolderOpen, Loader2, SquarePen, FolderGit2, Check, ChevronRight } from "lucide-react";
import type { PenFile } from "../types/pen";
import {
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

const API = "";

interface Props {
  onIngested: (projectId: string, pen: PenFile) => void;
  onStartBlank: (projectId: string, pen: PenFile) => void;
  onLoadExample: (projectId: string, pen: PenFile) => void;
  onLoadNexusExercise: (projectId: string, pen: PenFile) => void;
  onLoadClaudeEval: (projectId: string, pen: PenFile) => void;
  onLoadRepoAnalysis: (projectId: string, pen: PenFile) => void;
}

const REPO_ANALYSIS_STEPS = [
  "Indexing repository files…",
  "Parsing Python with ast…",
  "Parsing TypeScript with regex…",
  "Building call graph…",
  "Inferring entities from Pydantic models…",
  "Inferring DFD processes from FastAPI routes…",
  "Composing PenFile…",
];

const DEMO_REPOS = [
  {
    id: "dfdmaker",
    name: "DFDMaker",
    path: "C:\\Users\\ajfil\\Documents\\Github\\DFDMaker",
    description: "This project — FastAPI backend + React frontend",
    branch: "main",
  },
];

export function UploadPanel({
  onIngested,
  onStartBlank,
  onLoadExample,
  onLoadNexusExercise,
  onLoadClaudeEval,
  onLoadRepoAnalysis,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repoAnalyzing, setRepoAnalyzing] = useState(false);
  const [repoStep, setRepoStep] = useState(0);
  const [repoPicking, setRepoPicking] = useState(false);
  const [repoPath, setRepoPath] = useState(DEMO_REPOS[0].path);
  const [activeRepoPath, setActiveRepoPath] = useState(DEMO_REPOS[0].path);
  const repoFolderRef = useRef<HTMLInputElement>(null);
  const openFileRef = useRef<HTMLInputElement>(null);

  const upload = useCallback(async (files: File[]) => {
    if (!files.length) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      const projectName = files[0].name.replace(/\.[^.]+$/, "");
      const res = await fetch(
        `${API}/ingest/spreadsheet?project_name=${encodeURIComponent(projectName)}`,
        { method: "POST", body: form }
      );
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg);
      }
      const data = await res.json();
      onIngested(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }, [onIngested]);

  const handleStartBlank = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/schema/blank`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onStartBlank(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create blank project");
    } finally {
      setLoading(false);
    }
  }, [onStartBlank]);

  const handleLoadExample = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/schema/example`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onLoadExample(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load example schema");
    } finally {
      setLoading(false);
    }
  }, [onLoadExample]);

  const handleLoadClaudeEval = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/schema/claude-eval`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onLoadClaudeEval(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load Claude eval");
    } finally {
      setLoading(false);
    }
  }, [onLoadClaudeEval]);

  const handleAnalyzeRepo = useCallback(async () => {
    const targetPath = repoPath.trim();
    if (!targetPath) {
      setError("Repository path is required");
      return;
    }
    setActiveRepoPath(targetPath);
    setError(null);
    setRepoAnalyzing(true);
    setRepoStep(0);

    const stepInterval = window.setInterval(() => {
      setRepoStep((prev) => Math.min(prev + 1, REPO_ANALYSIS_STEPS.length - 1));
    }, 450);

    try {
      const fetchPromise = analyzeRepository(targetPath);
      const minDelay = new Promise((resolve) => window.setTimeout(resolve, REPO_ANALYSIS_STEPS.length * 450 + 200));
      const [data] = await Promise.all([fetchPromise, minDelay]);
      window.clearInterval(stepInterval);
      setRepoStep(REPO_ANALYSIS_STEPS.length);
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      onLoadRepoAnalysis(data.project_id, data.pen);
    } catch (e: unknown) {
      window.clearInterval(stepInterval);
      setError(e instanceof Error ? e.message : "Repo analysis failed");
    } finally {
      setRepoAnalyzing(false);
    }
  }, [onLoadRepoAnalysis, repoPath]);

  const handleAnalyzeRepoFolder = useCallback(async (files: FileList | null) => {
    if (!files?.length) return;
    const folderName = folderNameFromFiles(files);
    setActiveRepoPath(folderName);
    setError(null);
    setRepoAnalyzing(true);
    setRepoStep(0);

    const stepInterval = window.setInterval(() => {
      setRepoStep((prev) => Math.min(prev + 1, REPO_ANALYSIS_STEPS.length - 1));
    }, 450);

    try {
      const fetchPromise = analyzeRepositoryFolder(files);
      const minDelay = new Promise((resolve) => window.setTimeout(resolve, REPO_ANALYSIS_STEPS.length * 450 + 200));
      const [data] = await Promise.all([fetchPromise, minDelay]);
      window.clearInterval(stepInterval);
      setRepoStep(REPO_ANALYSIS_STEPS.length);
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      onLoadRepoAnalysis(data.project_id, data.pen);
    } catch (e: unknown) {
      window.clearInterval(stepInterval);
      setError(e instanceof Error ? e.message : "Repo analysis failed");
    } finally {
      setRepoAnalyzing(false);
      if (repoFolderRef.current) repoFolderRef.current.value = "";
    }
  }, [onLoadRepoAnalysis]);

  const handleLoadNexusExercise = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/schema/nexus-exercise`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      onLoadNexusExercise(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load Nexus exercise");
    } finally {
      setLoading(false);
    }
  }, [onLoadNexusExercise]);

  const handleOpenDfdFile = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await importDfdJsonFile(file);
      onIngested(data.project_id, data.pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to open file");
    } finally {
      setLoading(false);
      if (openFileRef.current) openFileRef.current.value = "";
    }
  }, [onIngested]);

  const handleOpenDfd = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    void handleOpenDfdFile(e.target.files?.[0]);
  }, [handleOpenDfdFile]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    const dfd = dropped.find((f) => /\.dfd\.json$/i.test(f.name));
    if (dfd) {
      void handleOpenDfdFile(dfd);
      return;
    }
    const files = dropped.filter((f) => /\.(xlsx|xls|csv)$/i.test(f.name));
    upload(files);
  }, [handleOpenDfdFile, upload]);

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    upload(files);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-8">
      <div className="text-center">
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">DataRoot</h1>
        <p className="text-gray-500 text-sm">
          Analyze a repo, upload spreadsheets, or open an existing project
        </p>
      </div>

      {/* Repo Analysis CTA */}
      <div className="w-full max-w-lg rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 overflow-hidden">
        <button
          onClick={() => setRepoPicking((v) => !v)}
          disabled={loading || repoAnalyzing}
          className="w-full flex items-center gap-4 p-4 hover:from-amber-100 hover:to-orange-100 hover:border-amber-300 transition-colors disabled:opacity-50 text-left"
        >
          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <FolderGit2 className="w-5 h-5 text-amber-700" />
          </div>
          <div className="flex-1">
            <div className="font-medium text-gray-900 text-sm">Analyze a repository locally</div>
            <div className="text-xs text-gray-500 mt-0.5">
              Generate one .dfd.json file, then import it here
            </div>
          </div>
          <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-200/60 text-amber-900 font-semibold">
            Local
          </span>
          <ChevronRight className={`w-4 h-4 text-amber-600 transition-transform ${repoPicking ? "rotate-90" : ""}`} />
        </button>

        {repoPicking && (
          <div className="border-t border-amber-200 px-4 py-3 bg-white/60">
            <button
              type="button"
              onClick={() => openFileRef.current?.click()}
              className="w-full py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-sm font-semibold transition-colors"
            >
              Import generated .dfd.json
            </button>
            <div className="mt-3 rounded-lg border border-amber-200 bg-white p-3">
              <div className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold mb-2">
                Generate locally
              </div>
              <pre className="whitespace-pre-wrap break-all rounded bg-gray-950 px-3 py-2 text-[11px] leading-5 text-amber-50">{LOCAL_ANALYZE_POWERSHELL}</pre>
              <pre className="mt-2 whitespace-pre-wrap break-all rounded bg-gray-950 px-3 py-2 text-[11px] leading-5 text-amber-50">{LOCAL_ANALYZE_BASH}</pre>
              <div className="mt-2 text-xs text-gray-500">
                Output: <span className="font-mono">{LOCAL_ANALYZE_OUTPUT}</span>
              </div>
            </div>
            {SERVER_REPO_ANALYSIS_ENABLED && (
              <>
                <div className="flex items-center gap-3 my-3">
                  <div className="flex-1 border-t border-amber-200" />
                  <span className="text-xs text-gray-400">local backend</span>
                  <div className="flex-1 border-t border-amber-200" />
                </div>
                <label className="block text-[11px] text-gray-500 uppercase tracking-wider font-semibold mb-2">
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
                  className="w-full rounded-lg border border-amber-200 bg-white px-3 py-2.5 text-sm font-mono text-gray-800 outline-none focus:border-amber-500"
                />
                <button
                  onClick={() => { setRepoPicking(false); handleAnalyzeRepo(); }}
                  disabled={!repoPath.trim()}
                  className="mt-3 w-full py-2 rounded-lg border border-amber-300 bg-white text-amber-800 text-sm font-semibold hover:border-amber-500 transition-colors disabled:opacity-50"
                >
                  Analyze {repoNameFromPath(repoPath)}
                </button>
                <button
                  type="button"
                  onClick={() => repoFolderRef.current?.click()}
                  className="mt-2 w-full py-2 rounded-lg border border-amber-300 bg-white text-amber-800 text-sm font-semibold hover:border-amber-500 transition-colors"
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

      <label
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`
          w-full max-w-lg border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-colors duration-150
          ${dragging
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 hover:border-gray-400 bg-white"
          }
        `}
      >
        <input
          type="file"
          accept=".xlsx,.xls,.csv"
          multiple
          className="hidden"
          onChange={onFileInput}
        />
        {loading ? (
          <div className="flex flex-col items-center gap-3 text-gray-500">
            <Loader2 className="w-10 h-10 animate-spin text-blue-500" />
            <span>Parsing spreadsheet…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 text-gray-500">
            <Upload className="w-10 h-10 text-gray-400" />
            <div>
              <span className="font-medium text-gray-700">Drop files here</span>
              <span className="text-gray-400"> or click to browse</span>
            </div>
            <div className="flex gap-2 mt-1">
              {[".xlsx", ".xls", ".csv"].map((ext) => (
                <span
                  key={ext}
                  className="px-2 py-0.5 bg-gray-100 rounded text-xs font-mono text-gray-600"
                >
                  {ext}
                </span>
              ))}
            </div>
          </div>
        )}
      </label>

      {/* "or" divider + starter actions */}
      <div className="flex items-center gap-3 w-full max-w-lg">
        <div className="flex-1 border-t border-gray-200" />
        <span className="text-sm text-gray-400">or</span>
        <div className="flex-1 border-t border-gray-200" />
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={() => openFileRef.current?.click()}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:border-indigo-400 hover:text-indigo-700 transition-colors disabled:opacity-50"
        >
          <FolderOpen className="w-4 h-4" />
          Open .dfd.json
        </button>
        <input
          ref={openFileRef}
          type="file"
          accept=".dfd.json,.json"
          className="hidden"
          onChange={handleOpenDfd}
        />
        <button
          onClick={handleLoadExample}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-indigo-200 bg-indigo-50 text-sm font-medium text-indigo-700 hover:border-indigo-400 hover:bg-indigo-100 transition-colors disabled:opacity-50"
        >
          <FileSpreadsheet className="w-4 h-4" />
          Load example schema
        </button>
        <button
          onClick={handleLoadNexusExercise}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-emerald-200 bg-emerald-50 text-sm font-medium text-emerald-700 hover:border-emerald-400 hover:bg-emerald-100 transition-colors disabled:opacity-50"
        >
          <Boxes className="w-4 h-4" />
          Nexus — Codex eval
        </button>
        <button
          onClick={handleLoadClaudeEval}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-violet-200 bg-violet-50 text-sm font-medium text-violet-700 hover:border-violet-400 hover:bg-violet-100 transition-colors disabled:opacity-50"
        >
          <BrainCircuit className="w-4 h-4" />
          Nexus — Claude eval
        </button>
        <button
          onClick={handleStartBlank}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:border-indigo-400 hover:text-indigo-700 transition-colors disabled:opacity-50"
        >
          <SquarePen className="w-4 h-4" />
          Start with a blank canvas
        </button>
      </div>

      {error && (
        <div className="w-full max-w-lg bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="flex gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1">
          <FileSpreadsheet className="w-4 h-4" /> Excel supported
        </span>
        <span className="flex items-center gap-1">
          <FileSpreadsheet className="w-4 h-4" /> CSV supported
        </span>
      </div>

      {repoAnalyzing && (
        <div className="fixed inset-0 z-50 bg-gray-900/40 backdrop-blur-sm flex items-center justify-center">
          <div className="w-full max-w-md bg-white rounded-xl shadow-2xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                <FolderGit2 className="w-5 h-5 text-amber-700" />
              </div>
              <div>
                <div className="font-semibold text-gray-900 text-sm">
                  Analyzing repository
                </div>
                <div className="text-xs text-gray-500 font-mono mt-0.5 break-all">
                  {activeRepoPath}
                </div>
              </div>
            </div>
            <ol className="space-y-2 text-sm">
              {REPO_ANALYSIS_STEPS.map((step, idx) => {
                const done = idx < repoStep;
                const active = idx === repoStep;
                return (
                  <li
                    key={step}
                    className={`flex items-center gap-2 transition-opacity ${
                      done || active ? "opacity-100" : "opacity-40"
                    }`}
                  >
                    <span className="w-5 h-5 flex-shrink-0 flex items-center justify-center">
                      {done ? (
                        <Check className="w-4 h-4 text-emerald-600" />
                      ) : active ? (
                        <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
                      ) : (
                        <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
                      )}
                    </span>
                    <span
                      className={
                        done
                          ? "text-gray-500 line-through decoration-emerald-300"
                          : active
                          ? "text-gray-900 font-medium"
                          : "text-gray-500"
                      }
                    >
                      {step}
                    </span>
                  </li>
                );
              })}
            </ol>
            <div className="mt-4 text-[11px] text-gray-400 italic">
              Generating diagrams from repository source.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
