import { useState } from "react";
import type { DiaryDay, DiaryEntry, Mealtime, Placement } from "../api";
import { MEALTIMES } from "../api";

/** What an entry being dragged carries: its id and where it sits now. */
interface DragRef {
  id: string;
  date: string;
  meal: Mealtime;
  idx: number;
}

interface Props {
  days: DiaryDay[];
  onAdd: (recipe: string, where: Placement) => void;
  onRemove: (id: string) => void;
  onMove: (id: string, where: Placement) => void;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function WeekGrid({ days, onAdd, onRemove, onMove }: Props) {
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
    const moved = e.dataTransfer.getData("text/entry");
    if (recipe) {
      onAdd(recipe, { date, mealtime: meal, position: before });
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

  const entryRow = (entry: DiaryEntry, date: string, meal: Mealtime, idx: number) => {
    const key = `${date}:${meal}:${idx}`;
    return (
      <div
        className={`entry${over === key ? " insert-before" : ""}`}
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
            <tr key={day.date}>
              <td className="day-cell">
                {DAY_NAMES[di] ?? ""}
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
