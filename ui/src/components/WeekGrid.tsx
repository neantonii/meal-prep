import { useState } from "react";
import type { DiaryDay, DiaryEntry, Link, Mealtime, Placement, Session } from "../api";
import { MEALTIMES, dayLabel } from "../api";
import type { ItemDrag } from "./SessionsBar";

/** What an entry being dragged carries: its id and where it sits now. */
interface DragRef {
  id: string;
  date: string;
  meal: Mealtime;
  idx: number;
}

interface Props {
  days: DiaryDay[];
  /** Sessions shown on the page (for badge labels). */
  sessions: Session[];
  /** Color class per session id. */
  colors: Record<string, string>;
  onAdd: (recipe: string, where: Placement, session: Link) => void;
  onRemove: (id: string) => void;
  onMove: (id: string, where: Placement) => void;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function WeekGrid({
  days,
  sessions,
  colors,
  onAdd,
  onRemove,
  onMove,
}: Props) {
  // Drop target highlight: a slot ("date:meal") or an entry ("date:meal:idx").
  const [over, setOver] = useState<string | null>(null);

  /**
   * Handle a drop into a slot. `before` is the index of the entry the drop
   * landed on (insert before it), or undefined for the slot itself (append).
   */
  const drop = (e: React.DragEvent, date: string, meal: Mealtime, before?: number) => {
    e.preventDefault();
    e.stopPropagation();
    setOver(null);
    const recipe = e.dataTransfer.getData("text/recipe-id");
    const item = e.dataTransfer.getData("text/session-item");
    const moved = e.dataTransfer.getData("text/entry");
    if (recipe) {
      onAdd(recipe, { date, mealtime: meal, position: before }, "auto");
    } else if (item) {
      const from = JSON.parse(item) as ItemDrag;
      onAdd(from.recipe, { date, mealtime: meal, position: before }, from.session);
    } else if (moved) {
      const from = JSON.parse(moved) as DragRef;
      let position = before;
      // Same slot, moving down: the entry's own removal shifts the target up.
      if (
        position !== undefined &&
        from.date === date &&
        from.meal === meal &&
        from.idx < position
      )
        position -= 1;
      if (from.date === date && from.meal === meal && position === from.idx) return;
      onMove(from.id, { date, mealtime: meal, position });
    }
  };

  /** A date badge only for a link to an unusual session (not the latest
   * one before the entry's day); the usual one shows as the edge color. */
  const badge = (entry: DiaryEntry) => {
    if (!entry.session || !entry.unusual_session) return null;
    const source = sessions.find((s) => s.id === entry.session);
    return (
      <span
        className={`badge ${colors[entry.session] ?? ""}`}
        title="From a session other than the latest one before this day"
      >
        {source ? dayLabel(source.date) : "prep ?"}
      </span>
    );
  };

  /** Edge color: the session's color, or the unlinked color. */
  const edge = (entry: DiaryEntry) =>
    entry.session ? `linked ${colors[entry.session] ?? ""}` : "unlinked";

  const entryRow = (
    entry: DiaryEntry,
    date: string,
    meal: Mealtime,
    idx: number,
  ) => {
    const key = `${date}:${meal}:${idx}`;
    return (
      <div
        className={`entry ${edge(entry)}${over === key ? " insert-before" : ""}`}
        title={entry.session ? undefined : "Not from a prep session"}
        key={entry.id}
        draggable
        onDragStart={(e) =>
          e.dataTransfer.setData(
            "text/entry",
            JSON.stringify({ id: entry.id, date, meal, idx } satisfies DragRef),
          )
        }
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOver(key);
        }}
        onDragLeave={() => setOver((o) => (o === key ? null : o))}
        onDrop={(e) => drop(e, date, meal, idx)}
      >
        {entry.card_url ? (
          <a href={entry.card_url} target="_blank" rel="noreferrer">
            {entry.title}
          </a>
        ) : (
          <span title="This recipe no longer exists">{entry.title}</span>
        )}
        {badge(entry)}
        <span className="kcal">{Math.round(entry.kcal)}</span>
        <button className="x" title="Remove" onClick={() => onRemove(entry.id)}>
          ×
        </button>
      </div>
    );
  };

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
              {MEALTIMES.map((mt) => {
                const key = `${day.date}:${mt}`;
                const entries = day.meals.find((m) => m.mealtime === mt)?.entries ?? [];
                return (
                  <td key={mt}>
                    <div
                      className={`slot${over === key ? " dragover" : ""}`}
                      onDragOver={(e) => {
                        e.preventDefault();
                        setOver(key);
                      }}
                      onDragLeave={() => setOver((o) => (o === key ? null : o))}
                      onDrop={(e) => drop(e, day.date, mt)}
                    >
                      {entries.length === 0 ? (
                        <span className="empty-slot">—</span>
                      ) : (
                        entries.map((entry, idx) => entryRow(entry, day.date, mt, idx))
                      )}
                    </div>
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
