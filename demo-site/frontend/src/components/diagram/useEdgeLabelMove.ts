import { useContext } from "react";
import { EdgeLabelDragContext } from "./edgeLabelDragContext";

export function useEdgeLabelMove() {
  return useContext(EdgeLabelDragContext);
}
