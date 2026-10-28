import { useDndContext, useDroppable } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { DiaryDay, DiaryEntry, Mealtime, Session } from "../api";
import { MEALTIMES, dayLabel, sessionColor } from "../api";
import { slotId, type DragData, type DropData } from "../dnd";

interface Props {
  days: DiaryDay[];
  /** Sessions shown on the page (for badge labels). */
  sessions: Session[];
  /** Color class per session id. */
  colors: Record<string, string>;
  /** Monday of the page's week (for the standard session slots). */
  monday: string;
  onRemove: (id: string) => void;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
// Color classes of the four standard session slots (see sessionColor).
const STANDARD = new Set(["c0", "c1", "c2", "c3"]);

/** The week table. Meals are sortable within and across slots; the drop
 * logic itself lives in App's onDragEnd. */
export default function WeekGrid({ days, sessions, colors, monday, onRemove }: Props) {
  return (
    <table className="grid">
      <thead>
        <tr>
          <th>Day</th>
          {MEALTIMES.map((m) => (
            <th key={m}>{m}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {days.map((day, di) => {
          const t = day.totals;
          return (
            <tr key={day.date} className={`day ${day.mode}`}>
              <td className="day-cell">
                {DAY_NAMES[di] ?? ""} <span className={`mode-tag ${day.mode}`}>{day.mode}</span>
                <span className="date">{day.date}</span>
                <span className="day-total">
                  {Math.round(t["kcal"] ?? 0)} kcal · {Math.round(t["protein_g"] ?? 0)}P ·{" "}
                  {Math.round(t["carbs_g"] ?? 0)}C · {Math.round(t["fat_g"] ?? 0)}F
                </span>
              </td>
              {MEALTIMES.map((mt) => (
                <Slot
                  key={mt}
                  date={day.date}
                  meal={mt}
                  entries={day.meals.find((m) => m.mealtime === mt)?.entries ?? []}
                  sessions={sessions}
                  colors={colors}
                  monday={monday}
                  onRemove={onRemove}
                />
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

type SlotProps = Omit<Props, "days"> & {
  date: string;
  meal: Mealtime;
  entries: DiaryEntry[];
};

/** One table cell: a drop target holding a sortable list of meals. */
function Slot({ date, meal, entries, ...rest }: SlotProps) {
  const id = slotId(date, meal);
  const { setNodeRef } = useDroppable({ id, data: { kind: "slot", date, meal } satisfies DropData });
  const { active, over } = useDndContext();
  const dragging = active?.data.current as DragData | undefined;
  const target = over?.data.current as DropData | undefined;
  // Highlight the slot a drop would land in (the slot itself or one of its meals).
  const hovered =
    dragging !== undefined &&
    target !== undefined &&
    target.kind !== "session" &&
    target.date === date &&
    target.meal === meal;
  return (
    <td ref={setNodeRef} className={`slot-cell${hovered ? " dragover" : ""}`}>
      <SortableContext id={id} items={entries.map((e) => e.id)} strategy={verticalListSortingStrategy}>
        <div className="slot">
          {entries.length === 0 ? (
            <span className="empty-slot">—</span>
          ) : (
            entries.map((entry, index) => (
              <EntryRow key={entry.id} entry={entry} date={date} meal={meal} index={index} {...rest} />
            ))
          )}
        </div>
      </SortableContext>
    </td>
  );
}

type EntryProps = Omit<SlotProps, "entries"> & { entry: DiaryEntry; index: number };

/** One meal: sortable (drag to reorder or move), with its session edge. */
function EntryRow({ entry, date, meal, index, sessions, colors, monday, onRemove }: EntryProps) {
  const data = {
    kind: "entry",
    id: entry.id,
    date,
    meal,
    index,
    title: entry.title,
  } satisfies DragData & DropData;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging, isOver, active } =
    useSortable({ id: entry.id, data });
  const from = active?.data.current as DragData | undefined;
  // Another slot's meal, a recipe or a session item hovering here: it will
  // be inserted around this meal, so show the line.
  const incoming =
    isOver && from !== undefined && !(from.kind === "entry" && from.date === date && from.meal === meal);

  /** A date badge only when the source is not one of the page's four
   * standard sessions (Sun before, Tue, Thu, own Sun): those are told apart
   * by the edge color alone. */
  const badge = () => {
    if (!entry.session) return null;
    const source = sessions.find((s) => s.id === entry.session);
    if (source && STANDARD.has(sessionColor(source.date, monday))) return null;
    return (
      <span className={`badge ${colors[entry.session] ?? ""}`} title="From a session outside the four standard ones">
        {source ? dayLabel(source.date) : "prep ?"}
      </span>
    );
  };
  const edge = entry.session ? `linked ${colors[entry.session] ?? ""}` : "unlinked";

  return (
    <div
      ref={setNodeRef}
      className={`entry ${edge}${isDragging ? " dragging" : ""}${incoming ? " incoming" : ""}`}
      style={{ transform: CSS.Translate.toString(transform), transition }}
      title={entry.session ? undefined : "Not from a prep session"}
      {...attributes}
      {...listeners}
    >
      {entry.card_url ? (
        <a href={entry.card_url} target="_blank" rel="noreferrer">
          {entry.title}
        </a>
      ) : (
        <span title="This recipe no longer exists">{entry.title}</span>
      )}
      {badge()}
      <span className="kcal">{Math.round(entry.kcal)}</span>
      <button
        className="x"
        title="Remove"
        onKeyDown={(e) => e.stopPropagation()}
        onClick={() => onRemove(entry.id)}
      >
        ×
      </button>
    </div>
  );
}
