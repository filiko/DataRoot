import { assignHandles } from "./handleAssignment";
import { placeEdgeLabels } from "./labelPlacement";
import { routeEdges } from "./orthogonalRouter";
import type { LayoutEdgeRef, LayoutNodeBox, RoutedEdge } from "./types";

type HandledEdge = LayoutEdgeRef & { sourceHandle: string; targetHandle: string };

function hasHandles(edge: LayoutEdgeRef): edge is HandledEdge {
  return Boolean(edge.sourceHandle && edge.targetHandle);
}

/**
 * Compute orthogonal routes and label positions for display, without persisting
 * anything. Edges that already carry a stored route (points >= 2) are kept as-is
 * and treated as obstacles; edges missing a route are assigned handles (only when
 * absent) and routed against the stored node boxes. Pure and synchronous — safe
 * to call from a render path (penToFlow / dfdToFlow).
 */
export function computeDisplayEdgeLayout(
  nodes: LayoutNodeBox[],
  edges: LayoutEdgeRef[],
): RoutedEdge[] {
  // Edges with a full stored route (points >= 2) keep it; the rest get routed.
  // In both cases, preserve stored/manual handles and only assign where absent.
  const withRoute: RoutedEdge[] = [];
  const handled: RoutedEdge[] = [];
  const missingHandles: LayoutEdgeRef[] = [];

  for (const edge of edges) {
    if (!hasHandles(edge)) {
      missingHandles.push(edge);
    } else if ((edge.points?.length ?? 0) >= 2) {
      withRoute.push({ ...edge, points: edge.points ?? [] });
    } else {
      handled.push({ ...edge, points: edge.points ?? [] });
    }
  }
  const assigned = assignHandles(nodes, missingHandles);

  // Stored routes first so they seed previousRoutes as crossing obstacles;
  // reuseExistingPoints keeps them untouched while the rest route around them.
  const routed = routeEdges(nodes, [...withRoute, ...handled, ...assigned], {
    reuseExistingPoints: true,
  });
  return placeEdgeLabels(nodes, routed);
}
