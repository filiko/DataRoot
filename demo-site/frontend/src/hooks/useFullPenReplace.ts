import { useCallback, useState } from "react";
import type { PenFile } from "../types/pen";

const API = "";

export function useFullPenReplace(projectId: string) {
  const [saving, setSaving] = useState(false);

  const replacePen = useCallback(async (pen: PenFile): Promise<PenFile> => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/schema/${projectId}/pen`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pen),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  return { replacePen, saving };
}
