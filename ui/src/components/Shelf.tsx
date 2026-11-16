import { useDndContext, useDraggable, useDroppable } from "@dnd-kit/core";
import { useState } from "react";
import type { Bin, BinnedMeal, UnassignedRecipe } from "../api";
import { dayLabel } from "../api";
import type { DragData, DropData } from "../dnd";

interface Props {
  unassigned: UnassignedRecipe[];
  bin: Bin;
  /** Server's today (ISO date): the bin lists the last few days by default. */
  today: string;
}

// The bin lists what was binned in the last few days; the rest on demand.
const RECENT_DAYS = 3;

function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000);
}

/** Whether what is being dragged is a meal this slot takes. */
function useSlotDrop(slot: "unassigned" | "bin", takes: DragData["kind"][]) {
  const { setNodeRef, isOver } = useDroppable({ id: `slot:${slot}`, data: { kind: slot } satisfies DropData });
  const { active } = useDndContext();
  const kind = (active?.data.current as DragData | undefined)?.kind;
  return { setNodeRef, hint: isOver && kind !== undefined && takes.includes(kind) };
}

/** The two homes without a date, above the recipe list: portions with no
 * day yet (drag one to a day; drop a meal here to take it off its day) and
 * the bin (drop a meal to throw it away; drag it back out to undo). */
export default function Shelf({ unassigned, bin, today }: Props) {
  return (
    <>
      <Unassigned rows={unassigned} />
      <BinSection bin={bin} today={today} />
    </>
  );
}

function Unassigned({ rows }: { rows: UnassignedRecipe[] }) {
  const { setNodeRef, hint } = useSlotDrop("unassigned", ["entry", "binned"]);
  const total = rows.reduce((n, r) => n + r.count, 0);
  return (
    <section ref={setNodeRef} className={`shelf${hint ? " dragover" : ""}`}>
      <div className="shelf-title" title="Portions of prep sessions that are on no day yet">
        Unassigned <span className="muted">{total > 0 ? total : ""}</span>
      </div>
      {hint ? (
        <span className="empty-slot">drop to take it off its day</span>
      ) : rows.length === 0 ? (
        <span className="empty-slot">every portion has a day</span>
      ) : (
        rows.map((row) => <UnassignedRow key={row.recipe} row={row} />)
      )}
    </section>
  );
}

function UnassignedRow({ row }: { row: UnassignedRecipe }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `unassigned:${row.recipe}`,
    data: { kind: "unassigned", recipe: row.recipe, id: row.meals[0], title: row.title } satisfies DragData,
  });
  const from = row.sources.map((s) => `${s.count} from ${dayLabel(s.date)}`).join(" · ");
  return (
    <div
      ref={setNodeRef}
      className={`chip${isDragging ? " dragging" : ""}`}
      title={`${from}. Drag to a day to eat it then.`}
      {...attributes}
      {...listeners}
    >
      {row.card_url ? (
        <a href={row.card_url} target="_blank" rel="noreferrer">
          {row.title}
        </a>
      ) : (
        row.title
      )}{" "}
      <strong className="count">×{row.count}</strong>
      {row.freezer_friendly === false && (
        <span className="no-freeze" title="This dish doesn't freeze well: eat it while it keeps in the fridge">
          {" "}
          ⚠
        </span>
      )}{" "}
      <span className="kcal">
        {Math.round(row.kcal)} kcal · {Math.round(row.protein_g)}P
      </span>
    </div>
  );
}

function BinSection({ bin, today }: { bin: Bin; today: string }) {
  const { setNodeRef, hint } = useSlotDrop("bin", ["entry", "unassigned"]);
  const [older, setOlder] = useState(false);
  const recent = bin.meals.filter((m) => daysBetween(m.binned, today) < RECENT_DAYS);
  const shown = older ? bin.meals : recent;
  const hidden = bin.meals.length - recent.length;
  return (
    <details ref={setNodeRef} className={`shelf bin${hint ? " dragover" : ""}`} open={hint || undefined}>
      <summary className="shelf-title" title="Portions thrown away: they still count toward what was cooked">
        Bin{" "}
        <span className="muted">
          {hint ? "drop to throw it away" : bin.count > 0 ? `${bin.count} · $${bin.cost.toFixed(2)}` : "empty"}
        </span>
      </summary>
      {shown.map((meal) => (
        <BinnedRow key={meal.id} meal={meal} />
      ))}
      {hidden > 0 && (
        <button className="shelf-more" onClick={() => setOlder((o) => !o)}>
          {older ? "hide older" : `show ${hidden} older`}
        </button>
      )}
    </details>
  );
}

function BinnedRow({ meal }: { meal: BinnedMeal }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `binned:${meal.id}`,
    data: { kind: "binned", id: meal.id, title: meal.title } satisfies DragData,
  });
  return (
    <div
      ref={setNodeRef}
      className={`chip binned${isDragging ? " dragging" : ""}`}
      title={`Binned ${dayLabel(meal.binned)}${meal.session_date ? `, cooked ${dayLabel(meal.session_date)}` : ""}. Drag back to a day or to Unassigned to undo.`}
      {...attributes}
      {...listeners}
    >
      {meal.title} <span className="kcal">{dayLabel(meal.binned)}</span>
    </div>
  );
}
