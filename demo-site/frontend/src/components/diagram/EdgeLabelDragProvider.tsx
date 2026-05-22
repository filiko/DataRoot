import type { ReactNode } from "react";
import { EdgeLabelDragContext, type EdgeLabelMoveHandler } from "./edgeLabelDragContext";

export function EdgeLabelDragProvider({
  onLabelMove,
  children,
}: {
  onLabelMove: EdgeLabelMoveHandler;
  children: ReactNode;
}) {
  return (
    <EdgeLabelDragContext.Provider value={onLabelMove}>
      {children}
    </EdgeLabelDragContext.Provider>
  );
}
