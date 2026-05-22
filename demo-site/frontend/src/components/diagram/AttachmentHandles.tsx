import React from "react";
import { Handle } from "@xyflow/react";
import {
  ATTACHMENT_SIDES,
  HANDLE_LANES,
  HANDLE_POSITION,
  handleId,
  handleStyle,
} from "./attachmentHandleUtils";

interface AttachmentHandlesProps {
  visible: boolean;
  sourceTitle?: string;
  targetTitle?: string;
  sourceColor?: string;
  targetColor?: string;
  sourceBorder?: string;
  targetBorder?: string;
}

export function AttachmentHandles({
  visible,
  sourceTitle = "Drag from here",
  targetTitle = "Drop here",
  sourceColor = "#6366f1",
  targetColor = "#fff",
  sourceBorder = "#fff",
  targetBorder = "#6366f1",
}: AttachmentHandlesProps) {
  return (
    <>
      {ATTACHMENT_SIDES.map((side) =>
        HANDLE_LANES.map((lane) => (
          <React.Fragment key={`${side}-${lane}`}>
            <Handle
              id={handleId("target", side, lane)}
              type="target"
              position={HANDLE_POSITION[side]}
              title={targetTitle}
              style={handleStyle(side, lane, "target", visible, targetColor, targetBorder)}
            />
            <Handle
              id={handleId("source", side, lane)}
              type="source"
              position={HANDLE_POSITION[side]}
              title={sourceTitle}
              style={handleStyle(side, lane, "source", visible, sourceColor, sourceBorder)}
            />
          </React.Fragment>
        )),
      )}
    </>
  );
}
