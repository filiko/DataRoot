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

// Nexus Agriscience — target ERD, split per business process with seams lit up.
// Files are hand-authored under frontend/public/nexus/ and validated against PenFile.
// Master first (the whole-platform connection map), then one file per business process.
export const NEXUS_PROJECTS: DemoProject[] = [
  { id: "nexus-00-master",          label: "★ Master",             file: "/nexus/00_nexus_master.dfd.json"        },
  { id: "nexus-01-identity",        label: "01 Identity",          file: "/nexus/01_identity.dfd.json"            },
  { id: "nexus-02-control-numbers", label: "02 Control Numbers",   file: "/nexus/02_control_numbers.dfd.json"     },
  { id: "nexus-03-genetics",        label: "03 Genetics",          file: "/nexus/03_genetics.dfd.json"            },
  { id: "nexus-04-cultivation",     label: "04 Cultivation+Harvest", file: "/nexus/04_cultivation_harvest.dfd.json" },
  { id: "nexus-05-refinement",      label: "05 Refinement+Packaging", file: "/nexus/05_refinement_packaging.dfd.json" },
  { id: "nexus-06-qa-lab",          label: "06 QA / Lab",          file: "/nexus/06_qa_lab.dfd.json"              },
  { id: "nexus-07-quality",         label: "07 Quality+Batch",     file: "/nexus/07_quality_batch.dfd.json"       },
  { id: "nexus-08-product-master",  label: "08 Product Master",    file: "/nexus/08_product_master.dfd.json"      },
  { id: "nexus-09-consumer",        label: "09 Consumer Profile",  file: "/nexus/09_consumer_profile.dfd.json"    },
  { id: "nexus-10-sales",           label: "10 Sales / CRM",       file: "/nexus/10_sales.dfd.json"               },
  { id: "nexus-11-finance-ai",      label: "11 Finance + AI",      file: "/nexus/11_finance_ai.dfd.json"          },
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
