import { useState } from "react";
import type { Session, SessionItem } from "../api";
import { dayLabel, sessionColor } from "../api";

/** What a session item being dragged into a slot carries. */
export interface ItemDrag {
  session: string;
  recipe: string;
}

interface Props {
  sessions: Session[];
  /** Server's today (ISO date): later days are in Plan. */
  today: string;
  /** Monday of the page's week: colors follow the session's slot in it. */
  monday: string;
  /** Extra placeholder days the user added ("+ session"). */
  extraDates: string[];
  admin: boolean;
  onAddDate: (date: string) => void;
  onAddItem: (date: string, recipe: string) => void;
  onUpdateItem: (session: string, recipe: string, batches: number) => void;
  onRemoveItem: (session: string, recipe: string) => void;
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

function batchLabel(batches: number): string {
  return `${batches} batch${batches === 1 ? "" : "es"}`;
}

/** Warning for an underused batch: portions made but not planned/eaten. */
function Spare({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span
      className="spare"
      title={`${count} portion${count === 1 ? "" : "s"} made but not linked to a meal`}
    >
      ⚠ {count} spare
    </span>
  );
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
  monday,
  onAddItem,
  onLinkEntry,
}: Props & { session: Session; open: boolean; onToggle: () => void }) {
  const { id, date, mode, items } = session;
  const drop = useSessionDrop(
    (recipe) => onAddItem(date, recipe),
    id ? (entry) => onLinkEntry(entry, id) : undefined,
  );
  const spare = items.reduce((n, it) => n + it.portions - it.eaten, 0);
  return (
    <button
      className={`session-chip ${mode}${open ? " open" : ""}${id ? "" : " placeholder"}${drop.hint ? " dragover" : ""}`}
      onClick={onToggle}
      title={open ? "Close" : "Open this session"}
      {...drop.handlers}
    >
      <span className={`session-dot ${sessionColor(date, monday)}`} />
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
              : `${items.length} recipe${items.length === 1 ? "" : "s"}`}
      </span>
      {!drop.hint && <Spare count={spare} />}
    </button>
  );
}

function SessionPanel({
  session,
  onClose,
  monday,
  admin,
  onAddItem,
  onUpdateItem,
  onRemoveItem,
  onDelete,
  onLinkEntry,
}: Props & { session: Session; onClose: () => void }) {
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
      {admin ? (
        <input
          key={`${it.recipe}-${it.batches}`}
          className="batches"
          type="number"
          min={1}
          step={1}
          defaultValue={it.batches}
          title="Batches (Admin: correct what was made)"
          onBlur={(e) => {
            const batches = Number(e.target.value);
            if (id && Number.isInteger(batches) && batches >= 1 && batches !== it.batches)
              onUpdateItem(id, it.recipe, batches);
            else e.target.value = String(it.batches);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
      ) : (
        <span
          className="batches-text"
          title={
            mode === "plan"
              ? "Times the recipe is cooked; follows the planned meals"
              : "Times the recipe was cooked"
          }
        >
          {batchLabel(it.batches)}
        </span>
      )}
      <Spare count={it.portions - it.eaten} />
      <button className="x" title="Remove from session" onClick={() => id && onRemoveItem(id, it.recipe)}>
        ×
      </button>
    </div>
  );

  return (
    <div className={`session-panel ${mode}${drop.hint ? " dragover" : ""}`} {...drop.handlers}>
      <div className="session-head">
        <span className={`session-dot ${sessionColor(date, monday)}`} />
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
      {session.items.length === 0 ? (
        <span className="empty-slot">{canGrow ? "drop recipes here" : "nothing prepped"}</span>
      ) : (
        <div className="session-items">{session.items.map(item)}</div>
      )}
    </div>
  );
}
