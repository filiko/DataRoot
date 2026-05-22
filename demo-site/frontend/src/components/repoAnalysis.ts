import { API } from "../config/api";
import type { PenFile } from "../types/pen";

export const DEFAULT_REPO_PATH = "C:\\Users\\ajfil\\Documents\\Github\\DFDMaker";

export const SERVER_REPO_ANALYSIS_ENABLED =
  import.meta.env.VITE_ENABLE_SERVER_REPO_ANALYSIS === "1" || import.meta.env.DEV;

export const LOCAL_ANALYZE_POWERSHELL =
  ".\\scripts\\dfdmaker-analyze.ps1 -Repo C:\\path\\to\\repo";

export const LOCAL_ANALYZE_BASH =
  "./scripts/dfdmaker-analyze.sh /path/to/repo";

export const LOCAL_ANALYZE_OUTPUT = ".dfdmaker/project.dfd.json";

export const REPO_ANALYSIS_STEPS = [
  "Indexing repository files...",
  "Parsing Python with ast...",
  "Parsing TypeScript routes...",
  "Collecting FastAPI evidence...",
  "Accepting Phase A facts...",
  "Composing PenFile...",
  "Loading generated diagrams...",
];

export interface RepoAnalysisResponse {
  project_id: string;
  path: string;
  output_path: string;
  analysis: {
    route_count: number;
    process_count: number;
    pen_path: string;
  };
  pen: PenFile;
}

export interface ProjectImportResponse {
  project_id: string;
  pen: PenFile;
}

export function repoNameFromPath(path: string): string {
  const cleanPath = path.trim().replace(/[\\/]+$/, "");
  if (!cleanPath) return "repository";
  const parts = cleanPath.split(/[\\/]/);
  return parts[parts.length - 1] || "repository";
}

export async function analyzeRepository(repoPath: string): Promise<RepoAnalysisResponse> {
  const response = await fetch(API.repoAnalysis(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_path: repoPath.trim() }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export function folderNameFromFiles(files: FileList): string {
  const first = files.item(0) as (File & { webkitRelativePath?: string }) | null;
  const relativePath = first?.webkitRelativePath || first?.name || "selected repository";
  return relativePath.split(/[\\/]/)[0] || "selected repository";
}

export async function analyzeRepositoryFolder(files: FileList): Promise<RepoAnalysisResponse> {
  const form = new FormData();
  Array.from(files).forEach((file) => {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append("files", file, relativePath);
  });
  const response = await fetch(API.repoAnalysisUpload(), {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

export async function importDfdJsonFile(file: File): Promise<ProjectImportResponse> {
  const text = await file.text();
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error("That file is not valid JSON.");
  }

  const response = await fetch(API.importProject(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(json),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
