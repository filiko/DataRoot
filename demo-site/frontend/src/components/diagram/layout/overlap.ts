import { centerOf, inflateRect, rectsOverlap, snap } from "./geometry";
import type { LayoutNodeBox } from "./types";

export function repairNodeOverlaps(
  nodes: LayoutNodeBox[],
  gridSize: number,
  gap: number,
): LayoutNodeBox[] {
  // Snap first and push apart in grid multiples so the result is grid-aligned
  // by construction — a trailing snap could reintroduce the overlap it fixed.
  const next = nodes.map((node) => ({
    ...node,
    x: snap(node.x, gridSize),
    y: snap(node.y, gridSize),
  }));
  for (let iter = 0; iter < 80; iter++) {
    let changed = false;
    for (let i = 0; i < next.length; i++) {
      for (let j = i + 1; j < next.length; j++) {
        const a = next[i];
        const b = next[j];
        if (!rectsOverlap(inflateRect(a, gap / 2), inflateRect(b, gap / 2))) continue;

        const ac = centerOf(a);
        const bc = centerOf(b);
        const dx = bc.x - ac.x || ((i % 2 === 0) ? 1 : -1);
        const dy = bc.y - ac.y || ((j % 2 === 0) ? 1 : -1);
        const moveHorizontal = Math.abs(dx) >= Math.abs(dy);
        const amount = moveHorizontal
          ? (a.width + b.width) / 2 + gap - Math.abs(dx)
          : (a.height + b.height) / 2 + gap - Math.abs(dy);

        if (amount <= 0) continue;
        const direction = moveHorizontal ? Math.sign(dx) || 1 : Math.sign(dy) || 1;
        const half = Math.ceil(amount / 2 / gridSize) * gridSize;
        if (moveHorizontal) {
          a.x -= direction * half;
          b.x += direction * half;
        } else {
          a.y -= direction * half;
          b.y += direction * half;
        }
        changed = true;
      }
    }
    if (!changed) break;
  }

  return next;
}
