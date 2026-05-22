import { useCallback, useState } from "react";
import type { PenFile } from "../types/pen";

const API = "";

export interface ProjectOp {
  op: string;
  payload: Record<string, unknown>;
}

interface RunOpsOptions {
  baseRevision?: number;
  propagate?: boolean;
  doValidate?: boolean;
}

export function useProjectOps(projectId: string) {
  const [saving, setSaving] = useState(false);

  const runOps = useCallback(async (
    ops: ProjectOp[],
    options: RunOpsOptions = {},
  ): Promise<PenFile> => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/projects/${projectId}/ops`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ops,
          base_revision: options.baseRevision,
          propagate: options.propagate ?? false,
          do_validate: options.doValidate ?? true,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      return data.pen;
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  return { runOps, saving };
}
