import { centerOf, inflateRect, rectsOverlap, snap } from "./geometry";
import type { LayoutNodeBox } from "./types";

export function repairNodeOverlaps(
  nodes: LayoutNodeBox[],
  gridSize: number,
  gap: number,
): LayoutNodeBox[] {
  const next = nodes.map((node) => ({ ...node }));
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
        if (moveHorizontal) {
          a.x -= direction * amount / 2;
          b.x += direction * amount / 2;
        } else {
          a.y -= direction * amount / 2;
          b.y += direction * amount / 2;
        }
        changed = true;
      }
    }
    if (!changed) break;
  }

  return next.map((node) => ({
    ...node,
    x: snap(node.x, gridSize),
    y: snap(node.y, gridSize),
  }));
}
