import { useEffect, useRef } from "react";
import { API } from "../config/api";
import type { PenFile } from "../types/pen";

type Options = {
  projectId: string | null;
  currentRevision: number | undefined;
  onRefresh: (pen: PenFile) => void;
  enabled?: boolean;
  intervalMs?: number;
};

/**
 * Poll the server every `intervalMs` for the project's current revision.
 * If the server's revision is ahead of the client's, refetch the full pen
 * and call onRefresh. Skips while the tab is hidden.
 */
export function useProjectPolling({
  projectId,
  currentRevision,
  onRefresh,
  enabled = true,
  intervalMs = 2500,
}: Options) {
  const onRefreshRef = useRef(onRefresh);
  const revRef = useRef(currentRevision ?? 0);

  useEffect(() => {
    onRefreshRef.current = onRefresh;
  }, [onRefresh]);

  useEffect(() => {
    revRef.current = currentRevision ?? 0;
  }, [currentRevision]);

  useEffect(() => {
    if (!enabled || !projectId) return;

    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.hidden) return;
      try {
        const res = await fetch(API.projectRevision(projectId));
        if (!res.ok) return;
        const data: { revision: number } = await res.json();
        if (data.revision > revRef.current) {
          const penRes = await fetch(API.projects(projectId));
          if (!penRes.ok) return;
          const pen: PenFile = await penRes.json();
          if (!cancelled) {
            revRef.current = pen.project.revision;
            onRefreshRef.current(pen);
          }
        }
      } catch {
        // Silent — transient network errors shouldn't spam toasts.
      }
    };

    const handle = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [projectId, enabled, intervalMs]);
}
