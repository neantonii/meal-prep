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
  /** Relink a diary entry to a session (an entry dropped on it). */
  onLinkEntry: (entry: string, session: string) => void;
}

/** Drop target for a session: a palette recipe adds an item (`onRecipe`);
 * a diary entry relinks it to this session (`onEntry`, existing sessions
 * only). `hint` says which one is being dragged, for the label. */
function useSessionDrop(onRecipe: (recipe: string) => void, onEntry?: (entry: string) => void) {
  const [hint, setHint] = useState<"recipe" | "entry" | null>(null);
  return {
    hint,
    handlers: {
      onDragOver: (e: React.DragEvent) => {
        const types = e.dataTransfer.types;
        const kind = types.includes("text/recipe-id")
          ? "recipe"
          : types.includes("text/entry") && onEntry
            ? "entry"
            : null;
        if (!kind) return;
        e.preventDefault();
        setHint(kind);
      },
      onDragLeave: () => setHint(null),
      onDrop: (e: React.DragEvent) => {
        e.preventDefault();
        setHint(null);
        const recipe = e.dataTransfer.getData("text/recipe-id");
        const entry = e.dataTransfer.getData("text/entry");
        if (recipe) onRecipe(recipe);
        else if (entry && onEntry) onEntry((JSON.parse(entry) as { id: string }).id);
      },
    },
  };
}

/** Sessions above the week grid: a strip of one-line chips (older linked
 * sessions, then the Sunday before through this Sunday) and, below it, the
 * items of the one session that is open. */
export default function SessionsBar(props: Props) {
  const { sessions, extraDates, today, onAddDate } = props;
  const [newDate, setNewDate] = useState("");
  // The open session, by date: it stays open across week pages that show it.
  const [openDate, setOpenDate] = useState<string | null>(null);
  const shown = new Set(sessions.map((s) => s.date));
  const all: Session[] = [
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
  const open = all.find((s) => s.date === openDate) ?? null;

  return (
    <section className="sessions">
      <div className="session-strip">
        {all.map((s) => (
          <SessionChip
            key={s.id ?? s.date}
            session={s}
            open={s.date === openDate}
            onToggle={() => setOpenDate((d) => (d === s.date ? null : s.date))}
            {...props}
          />
        ))}
        <span className="add-session">
          <input type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} />
          <button
            disabled={!newDate}
            onClick={() => {
              onAddDate(newDate);
              setOpenDate(newDate);
              setNewDate("");
            }}
          >
            + session
          </button>
        </span>
      </div>
      {open && <SessionPanel session={open} onClose={() => setOpenDate(null)} {...props} />}
    </section>
  );
}

function SessionChip({
  session,
  open,
  onToggle,
  colors,
  onAddItem,
  onLinkEntry,
}: Props & { session: Session; open: boolean; onToggle: () => void }) {
  const { id, date, mode, items } = session;
  const drop = useSessionDrop(
    (recipe) => onAddItem(date, recipe),
    id ? (entry) => onLinkEntry(entry, id) : undefined,
  );
  const made = items.reduce((n, it) => n + it.portions, 0);
  const eaten = items.reduce((n, it) => n + it.eaten, 0);
  return (
    <button
      className={`session-chip ${mode}${open ? " open" : ""}${id ? "" : " placeholder"}${drop.hint ? " dragover" : ""}`}
      onClick={onToggle}
      title={open ? "Close" : "Open this session"}
      {...drop.handlers}
    >
      <span className={`session-dot ${id ? (colors[id] ?? "") : ""}`} />
      <strong>{dayLabel(date)}</strong>
      {!session.in_window && <span className="muted">earlier</span>}
      <span className={`mode-tag ${mode}`}>{mode}</span>
      <span className="muted">
        {drop.hint === "entry"
          ? "drop to link here"
          : drop.hint === "recipe"
            ? "drop to add"
            : items.length === 0
              ? "empty"
              : `${items.length} recipe${items.length === 1 ? "" : "s"} · ${eaten}/${made} eaten`}
      </span>
    </button>
  );
}

function SessionPanel({
  session,
  onClose,
  colors,
  admin,
  onAddItem,
  onUpdateItem,
  onRemoveItem,
  onMove,
  onDelete,
  onLinkEntry,
}: Props & { session: Session; onClose: () => void }) {
  const [moving, setMoving] = useState(false);
  const { id, date, mode } = session;
  // What the rules allow here (the server has the final say).
  const canGrow = admin || mode === "plan";
  const drop = useSessionDrop(
    (recipe) => onAddItem(date, recipe),
    id ? (entry) => onLinkEntry(entry, id) : undefined,
  );

  const item = (it: SessionItem) => (
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
      {it.card_url ? (
        <a className="item-title" href={it.card_url} target="_blank" rel="noreferrer" title={it.title}>
          {it.title}
        </a>
      ) : (
        <span className="item-title" title={`${it.title} (recipe no longer exists)`}>
          {it.title}
        </span>
      )}
      <input
        key={`${it.recipe}-${it.batches}`}
        className="batches"
        type="number"
        min={1}
        step={1}
        defaultValue={it.batches}
        title="Batches (times the recipe is made as written)"
        onBlur={(e) => {
          const batches = Number(e.target.value);
          if (id && Number.isInteger(batches) && batches >= 1 && batches !== it.batches)
            onUpdateItem(id, it.recipe, { batches });
          else e.target.value = String(it.batches);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
        }}
      />
      <span
        className={`made${it.eaten >= it.portions ? " full" : ""}`}
        title={`${it.eaten} eaten of ${it.portions} made`}
      >
        {it.eaten}/{it.portions}
      </span>
      <button
        className={`adhoc${it.ad_hoc ? " on" : ""}`}
        title={
          it.ad_hoc
            ? "Ad hoc: cooked at mealtime (click to unset)"
            : "Mark ad hoc: cooked at mealtime, not on prep day"
        }
        onClick={() => id && onUpdateItem(id, it.recipe, { ad_hoc: !it.ad_hoc })}
      >
        AH
      </button>
      <button className="x" title="Remove from session" onClick={() => id && onRemoveItem(id, it.recipe)}>
        ×
      </button>
    </div>
  );

  return (
    <div className={`session-panel ${mode}${drop.hint ? " dragover" : ""}`} {...drop.handlers}>
      <div className="session-head">
        <span className={`session-dot ${id ? (colors[id] ?? "") : ""}`} />
        <strong>{dayLabel(date)}</strong>
        <span className={`mode-tag ${mode}`}>{mode}</span>
        <span className="muted">
          {drop.hint === "entry"
            ? "drop to link this meal here"
            : canGrow
              ? "drop recipes here · drag items into slots · drop a meal to link it"
              : "drag items into slots · drop a meal to link it"}
        </span>
        <span className="session-actions">
          {id && canGrow && (
            <button title="Move to another day" onClick={() => setMoving((m) => !m)}>
              ⇄ move
            </button>
          )}
          {id && (
            <button title="Delete session" onClick={() => onDelete(id)}>
              delete
            </button>
          )}
          <button className="x" title="Close" onClick={onClose}>
            ×
          </button>
        </span>
      </div>
      {moving && id && (
        <input
          type="date"
          defaultValue={date}
          onChange={(e) => {
            if (e.target.value && e.target.value !== date) {
              onMove(id, e.target.value);
              setMoving(false);
              onClose();
            }
          }}
        />
      )}
      {session.items.length === 0 ? (
        <span className="empty-slot">{canGrow ? "drop recipes here" : "nothing prepped"}</span>
      ) : (
        <div className="session-items">{session.items.map(item)}</div>
      )}
    </div>
  );
}
