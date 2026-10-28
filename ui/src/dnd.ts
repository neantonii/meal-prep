/** Drag and drop (@dnd-kit): what can be dragged, where it can land, and
 * which target wins when several are under the pointer. */
import {
  pointerWithin,
  rectIntersection,
  type Active,
  type CollisionDetection,
  type Over,
} from "@dnd-kit/core";
import type { Mealtime } from "./api";

/** What is being dragged. */
export type DragData =
  | { kind: "recipe"; recipe: string; title: string }
  | { kind: "item"; session: string; recipe: string; title: string }
  | { kind: "entry"; id: string; date: string; meal: Mealtime; index: number; title: string };

/** Where it can land. Meals are both dragged and dropped on (sortable). */
export type DropData =
  | { kind: "slot"; date: string; meal: Mealtime }
  | { kind: "entry"; id: string; date: string; meal: Mealtime; index: number; title: string }
  | { kind: "session"; date: string; session: string | null };

export const slotId = (date: string, meal: Mealtime) => `slot:${date}:${meal}`;

/**
 * The target under the pointer, falling back to overlap (keyboard drags).
 * Within a slot, the nearest meal wins, so gaps between meals and the space
 * below the last one still pick a neighbour instead of "append".
 */
export const collision: CollisionDetection = (args) => {
  const hits = pointerWithin(args);
  const found = hits.length > 0 ? hits : rectIntersection(args);
  const data = (id: string | number) =>
    args.droppableContainers.find((d) => d.id === id)?.data.current as DropData | undefined;
  const direct = found.find((c) => data(c.id)?.kind === "entry");
  if (direct) return [direct];
  const target = found[0];
  const slot = target ? data(target.id) : undefined;
  if (!target || slot?.kind !== "slot") return target ? [target] : [];
  // Over a slot's empty space: snap to its nearest meal, if it has any.
  const y = args.pointerCoordinates?.y ?? args.collisionRect.top + args.collisionRect.height / 2;
  let best: { id: string | number; distance: number } | null = null;
  for (const container of args.droppableContainers) {
    const d = container.data.current as DropData | undefined;
    if (d?.kind !== "entry" || d.date !== slot.date || d.meal !== slot.meal) continue;
    const rect = args.droppableRects.get(container.id);
    if (!rect) continue;
    const distance = Math.abs(rect.top + rect.height / 2 - y);
    if (!best || distance < best.distance) best = { id: container.id, distance };
  }
  return best ? [{ id: best.id }] : [target];
};

/** True when the dragged thing's centre is below the target's centre. */
export function droppedBelow(active: Active, over: Over): boolean {
  const moved = active.rect.current.translated;
  if (!moved) return false;
  return moved.top + moved.height / 2 > over.rect.top + over.rect.height / 2;
}
