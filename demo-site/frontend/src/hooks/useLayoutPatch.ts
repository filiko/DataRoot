import { useCallback, useState } from "react";
import type { DiagramScope, PenFile } from "../types/pen";

const API = "";

export interface LayoutNodePatch {
  id: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface LayoutEdgePatch {
  id: string;
  route?: "orthogonal" | "straight" | "bezier";
  source_handle?: string | null;
  target_handle?: string | null;
  points?: Array<{ x: number; y: number }> | null;
  label_t?: number | null;
  label_offset?: number | null;
}

interface PatchLayoutInput {
  scope: DiagramScope;
  baseRevision?: number;
  nodes?: LayoutNodePatch[];
  edges?: LayoutEdgePatch[];
}

export function useLayoutPatch(projectId: string) {
  const [saving, setSaving] = useState(false);

  const patchLayout = useCallback(async ({
    scope,
    baseRevision,
    nodes = [],
    edges = [],
  }: PatchLayoutInput): Promise<PenFile> => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/schema/${projectId}/layout`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_revision: baseRevision,
          scope,
          nodes,
          edges,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  return { patchLayout, saving };
}
