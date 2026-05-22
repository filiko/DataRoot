import type { PenFile } from "../../types/pen";
import { API } from "../../config/api";

export interface DemoProject {
  id: string;
  label: string;
  file: string;
}

export const DEMO_PROJECTS: DemoProject[] = [
  { id: "austin-permits",   label: "Austin Permits",   file: "/austin_permits.dfd.json"           },
  { id: "example-store",    label: "Example Store",    file: "/example_store.dfd.json"            },
  { id: "dataroot-schema",  label: "DataRoot Schema",  file: "/dfdmaker_self.dfd.json"            },
  { id: "nexus-candidate",  label: "Nexus Candidate",  file: "/nexus_candidate_exercise.dfd.json" },
];

export async function loadDemoProject(demo: DemoProject = DEMO_PROJECTS[0]): Promise<{ projectId: string; pen: PenFile }> {
  const res = await fetch(demo.file);
  if (!res.ok) throw new Error("Could not load demo data");
  const pen = await res.json() as PenFile;

  // Try to register in backend so exports/validate/chat work (requires AUTH_DISABLED=1)
  try {
    const importRes = await fetch(API.importProject(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pen),
    });
    if (importRes.ok) {
      const { project_id, pen: registeredPen } = await importRes.json();
      return { projectId: project_id as string, pen: registeredPen as PenFile };
    }
  } catch {}

  return { projectId: demo.id, pen };
}
