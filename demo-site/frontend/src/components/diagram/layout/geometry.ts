import type { Point, Rect } from "./types";

export function centerOf(rect: Rect): Point {
  return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
}

export function inflateRect(rect: Rect, padding: number): Rect {
  return {
    ...rect,
    x: rect.x - padding,
    y: rect.y - padding,
    width: rect.width + padding * 2,
    height: rect.height + padding * 2,
  };
}

export function rectsOverlap(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.width
    && a.x + a.width > b.x
    && a.y < b.y + b.height
    && a.y + a.height > b.y;
}

export function overlapArea(a: Rect, b: Rect): number {
  const x = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
  const y = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  return x * y;
}

export function totalOverlapArea(rect: Rect, others: Rect[]): number {
  return others.reduce((sum, other) => sum + overlapArea(rect, other), 0);
}

export function snap(value: number, gridSize: number): number {
  return Math.round(value / gridSize) * gridSize;
}

export function snapPoint(point: Point, gridSize: number): Point {
  return { x: snap(point.x, gridSize), y: snap(point.y, gridSize) };
}

export function pointDistance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function polylineLength(points: Point[]): number {
  let length = 0;
  for (let i = 1; i < points.length; i++) {
    length += pointDistance(points[i - 1], points[i]);
  }
  return length;
}

export function polylineToPath(points: Point[]): string {
  if (points.length === 0) return "";
  return points.map((point, index) =>
    `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`
  ).join(" ");
}

export function dedupePolyline(points: Point[]): Point[] {
  const deduped: Point[] = [];
  for (const point of points) {
    const prev = deduped[deduped.length - 1];
    if (!prev || prev.x !== point.x || prev.y !== point.y) {
      deduped.push(point);
    }
  }

  const simplified: Point[] = [];
  for (const point of deduped) {
    simplified.push(point);
    while (simplified.length >= 3) {
      const a = simplified[simplified.length - 3];
      const b = simplified[simplified.length - 2];
      const c = simplified[simplified.length - 1];
      const sameX = a.x === b.x && b.x === c.x;
      const sameY = a.y === b.y && b.y === c.y;
      if (!sameX && !sameY) break;
      simplified.splice(simplified.length - 2, 1);
    }
  }
  return simplified;
}

export function labelSize(label: string | undefined): { width: number; height: number } {
  if (!label) return { width: 0, height: 0 };
  return {
    width: Math.min(220, label.length * 7 + 18),
    height: 22,
  };
}

export function alignRoutedPoints(
  points: Point[] | undefined,
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  tolerance = 40,
): Point[] | null {
  if (!points || points.length < 2) return null;
  const first = points[0];
  const last = points[points.length - 1];
  if (Math.hypot(first.x - sx, first.y - sy) > tolerance) return null;
  if (Math.hypot(last.x - tx, last.y - ty) > tolerance) return null;

  if (points.length === 2) {
    // A straight stored segment can't absorb anchor drift orthogonally; for
    // small drift (rendered handle centers sit a few px off the modeled
    // anchor) just connect the live anchors directly.
    const close = Math.hypot(first.x - sx, first.y - sy) < 16
      && Math.hypot(last.x - tx, last.y - ty) < 16;
    return close ? [{ x: sx, y: sy }, { x: tx, y: ty }] : null;
  }

  // Splice the live anchors into the route, shifting the adjacent point along
  // the shared axis so the terminal segments stay orthogonal.
  const next = points.map((point) => ({ ...point }));
  if (next[1].y === first.y) next[1] = { ...next[1], y: sy };
  else if (next[1].x === first.x) next[1] = { ...next[1], x: sx };
  next[0] = { x: sx, y: sy };

  const penultimate = next[next.length - 2];
  if (penultimate.y === last.y) next[next.length - 2] = { ...penultimate, y: ty };
  else if (penultimate.x === last.x) next[next.length - 2] = { ...penultimate, x: tx };
  next[next.length - 1] = { x: tx, y: ty };
  return next;
}

export function rectCenteredAt(id: string, center: Point, width: number, height: number): Rect {
  return {
    id,
    x: center.x - width / 2,
    y: center.y - height / 2,
    width,
    height,
  };
}

function pointInRect(point: Point, rect: Rect): boolean {
  return point.x >= rect.x
    && point.x <= rect.x + rect.width
    && point.y >= rect.y
    && point.y <= rect.y + rect.height;
}

export function segmentIntersectsRect(a: Point, b: Point, rect: Rect): boolean {
  if (pointInRect(a, rect) || pointInRect(b, rect)) return true;

  const minX = Math.min(a.x, b.x);
  const maxX = Math.max(a.x, b.x);
  const minY = Math.min(a.y, b.y);
  const maxY = Math.max(a.y, b.y);

  if (a.x === b.x) {
    return a.x >= rect.x
      && a.x <= rect.x + rect.width
      && maxY >= rect.y
      && minY <= rect.y + rect.height;
  }

  if (a.y === b.y) {
    return a.y >= rect.y
      && a.y <= rect.y + rect.height
      && maxX >= rect.x
      && minX <= rect.x + rect.width;
  }

  return lineIntersectsSegment(a, b, { x: rect.x, y: rect.y }, { x: rect.x + rect.width, y: rect.y })
    || lineIntersectsSegment(a, b, { x: rect.x + rect.width, y: rect.y }, { x: rect.x + rect.width, y: rect.y + rect.height })
    || lineIntersectsSegment(a, b, { x: rect.x + rect.width, y: rect.y + rect.height }, { x: rect.x, y: rect.y + rect.height })
    || lineIntersectsSegment(a, b, { x: rect.x, y: rect.y + rect.height }, { x: rect.x, y: rect.y });
}

export function segmentIntersectsSegment(a1: Point, a2: Point, b1: Point, b2: Point): boolean {
  return lineIntersectsSegment(a1, a2, b1, b2);
}

function lineIntersectsSegment(a1: Point, a2: Point, b1: Point, b2: Point): boolean {
  const direction = (a: Point, b: Point, c: Point) =>
    (c.x - a.x) * (b.y - a.y) - (b.x - a.x) * (c.y - a.y);
  const onSegment = (a: Point, b: Point, c: Point) =>
    Math.min(a.x, b.x) <= c.x && c.x <= Math.max(a.x, b.x)
    && Math.min(a.y, b.y) <= c.y && c.y <= Math.max(a.y, b.y);

  const d1 = direction(b1, b2, a1);
  const d2 = direction(b1, b2, a2);
  const d3 = direction(a1, a2, b1);
  const d4 = direction(a1, a2, b2);

  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0))
    && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
    return true;
  }
  if (d1 === 0 && onSegment(b1, b2, a1)) return true;
  if (d2 === 0 && onSegment(b1, b2, a2)) return true;
  if (d3 === 0 && onSegment(a1, a2, b1)) return true;
  if (d4 === 0 && onSegment(a1, a2, b2)) return true;
  return false;
}

export function pointAndNormalAtPolylineT(
  points: Point[],
  t: number,
  offset = 0,
): { point: Point; normal: Point; segmentIndex: number } {
  if (points.length === 0) {
    return { point: { x: 0, y: 0 }, normal: { x: 0, y: -1 }, segmentIndex: 0 };
  }
  if (points.length === 1) {
    return { point: points[0], normal: { x: 0, y: -1 }, segmentIndex: 0 };
  }

  const total = polylineLength(points);
  let remaining = Math.max(0, Math.min(1, t)) * total;

  for (let i = 1; i < points.length; i++) {
    const start = points[i - 1];
    const end = points[i];
    const segmentLength = pointDistance(start, end);
    if (remaining <= segmentLength || i === points.length - 1) {
      const ratio = segmentLength === 0 ? 0 : remaining / segmentLength;
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const normalLength = Math.hypot(dx, dy) || 1;
      const normal = { x: -dy / normalLength, y: dx / normalLength };
      const point = {
        x: start.x + dx * ratio + normal.x * offset,
        y: start.y + dy * ratio + normal.y * offset,
      };
      return { point, normal, segmentIndex: i - 1 };
    }
    remaining -= segmentLength;
  }

  return { point: points[points.length - 1], normal: { x: 0, y: -1 }, segmentIndex: points.length - 2 };
}

export function projectPointToPolyline(point: Point, points: Point[]): { t: number; offset: number; point: Point } {
  if (points.length < 2) {
    return { t: 0.5, offset: 0, point };
  }

  const total = polylineLength(points) || 1;
  let best = {
    distance: Number.POSITIVE_INFINITY,
    lengthAtPoint: 0,
    offset: 0,
    point: points[0],
  };
  let lengthBefore = 0;

  for (let i = 1; i < points.length; i++) {
    const start = points[i - 1];
    const end = points[i];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const segmentLengthSquared = dx * dx + dy * dy;
    const segmentLength = Math.sqrt(segmentLengthSquared);
    if (segmentLength === 0) continue;

    const rawRatio = ((point.x - start.x) * dx + (point.y - start.y) * dy) / segmentLengthSquared;
    const ratio = Math.max(0, Math.min(1, rawRatio));
    const projected = {
      x: start.x + dx * ratio,
      y: start.y + dy * ratio,
    };
    const normal = { x: -dy / segmentLength, y: dx / segmentLength };
    const offset = (point.x - projected.x) * normal.x + (point.y - projected.y) * normal.y;
    const distance = pointDistance(point, projected);

    if (distance < best.distance) {
      best = {
        distance,
        lengthAtPoint: lengthBefore + segmentLength * ratio,
        offset,
        point: projected,
      };
    }
    lengthBefore += segmentLength;
  }

  return {
    t: Math.max(0, Math.min(1, best.lengthAtPoint / total)),
    offset: Math.max(-80, Math.min(80, best.offset)),
    point: best.point,
  };
}
