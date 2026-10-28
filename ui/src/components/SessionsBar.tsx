import { useState } from "react";
import type { Session, SessionItem } from "../api";
import { dayLabel } from "../api";

/** What a session item being dragged into a slot carries. */
export interface ItemDrag {
  session: string;
  recipe: string;
}

interface Props {
  sessions: Session[];
  /** Server's today (ISO date): later days are in Plan. */
  today: string;
  /** Extra placeholder days the user added ("+ session"). */
  extraDates: string[];
  /** Badge color class per session id. */
  colors: Record<string, string>;
  admin: boolean;
  onAddDate: (date: string) => void;
  onAddItem: (date: string, recipe: string) => void;
  onUpdateItem: (session: string, recipe: string, change: { batches?: number; ad_hoc?: boolean }) => void;
  onRemoveItem: (session: string, recipe: string) => void;
  onMove: (session: string, date: string) => void;
  onDelete: (session: string) => void;
}

/** Session cards above the week grid: older linked sessions, then the
 * sessions from the Sunday before through this Sunday. */
export default function SessionsBar(props: Props) {
  const { sessions, extraDates, today, onAddDate } = props;
  const [newDate, setNewDate] = useState("");
  const shown = new Set(sessions.map((s) => s.date));
  const cards: Session[] = [
    ...sessions,
    ...extraDates
      .filter((d) => !shown.has(d))
      .map(
        (date): Session => ({
          id: null,
          date,
          mode: date > today ? "plan" : "log",
          in_window: true,
          items: [],
        }),
      ),
  ].sort((a, b) => Number(a.in_window) - Number(b.in_window) || a.date.localeCompare(b.date));

  return (
    <section className="sessions">
      {cards.map((s) => (
        <SessionCard key={s.id ?? s.date} session={s} {...props} />
      ))}
      <div className="session-card add-session">
        <span className="muted">+ session</span>
        <input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
        <button
          disabled={!newDate}
          onClick={() => {
            onAddDate(newDate);
            setNewDate("");
          }}
        >
          Add
        </button>
      </div>
    </section>
  );
}

function SessionCard({
  session,
  colors,
  admin,
  onAddItem,
  onUpdateItem,
  onRemoveItem,
  onMove,
  onDelete,
}: Props & { session: Session }) {
  const [over, setOver] = useState(false);
  const [moving, setMoving] = useState(false);
  const { id, date, mode } = session;
  // What the rules allow here (the server has the final say).
  const canGrow = admin || mode === "plan";
  const color = id ? colors[id] ?? "" : "";

  const item = (it: SessionItem) => {
    const full = it.eaten >= it.portions;
    return (
      <div
        className="session-item"
        key={it.recipe}
        draggable={id !== null}
        onDragStart={(e) =>
          e.dataTransfer.setData(
            "text/session-item",
            JSON.stringify({ session: id ?? "", recipe: it.recipe } satisfies ItemDrag),
          )
        }
        title="Drag into a slot to plan a serving from this session"
      >
        <div className="session-item-head">
          {it.card_url ? (
            <a href={it.card_url} target="_blank" rel="noreferrer">
              {it.title}
            </a>
          ) : (
            <span title="This recipe no longer exists">{it.title}</span>
          )}
          <button
            className="x"
            title="Remove from session"
            onClick={() => id && onRemoveItem(id, it.recipe)}
          >
            ×
          </button>
        </div>
        <div className="session-item-meta">
          <label title="Batches (times the recipe is made as written)">
            <input
              key={`${it.recipe}-${it.batches}`}
              className="batches"
              type="number"
              min={1}
              step={1}
              defaultValue={it.batches}
              onBlur={(e) => {
                const batches = Number(e.target.value);
                if (id && Number.isInteger(batches) && batches >= 1 && batches !== it.batches) onUpdateItem(id, it.recipe, { batches });
                else e.target.value = String(it.batches);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.currentTarget.blur();
              }}
            />
            ×
          </label>
          <span className={`made${full ? " full" : ""}`} title="portions made · eaten (linked entries)">
            {it.portions} made · {it.eaten} eaten
          </span>
          <label className="adhoc" title="Cooked at mealtime, not on prep day">
            <input
              type="checkbox"
              checked={it.ad_hoc}
              onChange={(e) => id && onUpdateItem(id, it.recipe, { ad_hoc: e.target.checked })}
            />
            ad hoc
          </label>
        </div>
      </div>
    );
  };

  return (
    <div
      className={`session-card ${mode}${over ? " dragover" : ""}${id ? "" : " placeholder"}`}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("text/recipe-id")) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const recipe = e.dataTransfer.getData("text/recipe-id");
        if (recipe) onAddItem(date, recipe);
      }}
    >
      <div className="session-head">
        <span className={`session-dot ${color}`} />
        <strong>{dayLabel(date)}</strong>
        {!session.in_window && <span className="muted">earlier</span>}
        <span className={`mode-tag ${mode}`}>{mode}</span>
        {id && (
          <span className="session-actions">
            {canGrow && (
              <button title="Move to another day" onClick={() => setMoving((m) => !m)}>
                ⇄
              </button>
            )}
            <button className="x" title="Delete session" onClick={() => onDelete(id)}>
              ×
            </button>
          </span>
        )}
      </div>
      {moving && id && (
        <input
          type="date"
          defaultValue={date}
          onChange={(e) => {
            if (e.target.value && e.target.value !== date) {
              onMove(id, e.target.value);
              setMoving(false);
            }
          }}
        />
      )}
      {session.items.length === 0 ? (
        <span className="empty-slot">{canGrow ? "drop recipes here" : "nothing prepped"}</span>
      ) : (
        session.items.map(item)
      )}
    </div>
  );
}
