import { createContext } from "react";

export type EdgeLabelMoveHandler = (edgeId: string, labelT: number, labelOffset: number) => void;

export const EdgeLabelDragContext = createContext<EdgeLabelMoveHandler | null>(null);
