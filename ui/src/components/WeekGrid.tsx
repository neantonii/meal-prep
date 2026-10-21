import { useState } from "react";
import type { CatalogEntry, DiaryDay, Mealtime } from "../api";
import { MEALTIMES } from "../api";

export interface MoveRef {
  day: number;
  meal: Mealtime;
  idx: number;
}

interface Props {
  days: DiaryDay[];
  byId: Map<string, CatalogEntry>;
  onAdd: (day: number, meal: Mealtime, id: string) => void;
  onRemove: (day: number, meal: Mealtime, idx: number) => void;
  onMove: (from: MoveRef, toDay: number, toMeal: Mealtime) => void;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function dayKcal(day: DiaryDay, byId: Map<string, CatalogEntry>): number {
  let kcal = 0;
  for (const m of day.meals)
    for (const id of m.recipes) kcal += byId.get(id)?.kcal ?? 0;
  return kcal;
}

export default function WeekGrid({ days, byId, onAdd, onRemove, onMove }: Props) {
  const [over, setOver] = useState<string | null>(null);

  const drop =
    (day: number, meal: Mealtime) => (e: React.DragEvent) => {
      e.preventDefault();
      setOver(null);
      const add = e.dataTransfer.getData("text/recipe-id");
      const move = e.dataTransfer.getData("text/move");
      if (add) onAdd(day, meal, add);
      else if (move) {
        const from = JSON.parse(move) as MoveRef;
        onMove(from, day, meal);
      }
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
        {days.map((day, di) => (
          <tr key={day.date}>
            <td className="day-cell">
              {DAY_NAMES[di] ?? ""}
              <span className="date">{day.date}</span>
              <span className="day-total">{Math.round(dayKcal(day, byId))} kcal</span>
            </td>
            {MEALTIMES.map((mt) => {
              const key = `${di}:${mt}`;
              const meal = day.meals.find((m) => m.mealtime === mt);
              return (
                <td key={mt}>
                  <div
                    className={`slot${over === key ? " dragover" : ""}`}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setOver(key);
                    }}
                    onDragLeave={() => setOver((o) => (o === key ? null : o))}
                    onDrop={drop(di, mt)}
                  >
                    {!meal || meal.recipes.length === 0 ? (
                      <span className="empty-slot">—</span>
                    ) : (
                      meal.recipes.map((id, ri) => {
                        const entry = byId.get(id);
                        return (
                          <div
                            className="entry"
                            key={`${id}:${ri}`}
                            draggable
                            onDragStart={(e) =>
                              e.dataTransfer.setData(
                                "text/move",
                                JSON.stringify({ day: di, meal: mt, idx: ri }),
                              )
                            }
                          >
                            <a
                              href={`/cards/recipe/${entry?.category ?? "unknown"}/${id}.html`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {entry?.title ?? id}
                            </a>
                            <span className="kcal">
                              {entry ? Math.round(entry.kcal) : "?"}
                            </span>
                            <button
                              className="x"
                              title="Remove"
                              onClick={() => onRemove(di, mt, ri)}
                            >
                              ×
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
