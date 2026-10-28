import { useDndContext, useDroppable } from "@dnd-kit/core";
import { useEffect, useRef, useState } from "react";
import type { Session, SessionItem } from "../api";
import { dayLabel, mealsLabel, sessionColor } from "../api";
import type { DragData, DropData } from "../dnd";

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
  onRemoveItem: (session: string, recipe: string) => void;
  onDelete: (session: string) => void;
  /** Open the session's own page. */
  onOpenDetails: (session: string) => void;
}

/** A session as a drop target (its chip or open panel): a meal dropped on
 * it relinks to it; an empty placeholder day gets its session created.
 * `hint` is true while a meal hovers. The drop itself is handled in App's
 * onDragEnd. */
function useSessionDrop(where: string, date: string, session: string | null) {
  const { setNodeRef, isOver } = useDroppable({
    id: `${where}:${date}`,
    data: { kind: "session", date, session } satisfies DropData,
  });
  const { active } = useDndContext();
  const kind = (active?.data.current as DragData | undefined)?.kind;
  const hint = isOver && kind === "entry";
  return { setNodeRef, hint };
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
 * sessions, then the Sunday before through this Sunday); the open one rolls
 * out over the week table. */
export default function SessionsBar(props: Props) {
  const { sessions, extraDates, today, admin, onAddDate } = props;
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
        {/* Sessions on non-standard days are rare: Admin only. */}
        {admin && (
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
        )}
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
}: Props & { session: Session; open: boolean; onToggle: () => void }) {
  const { id, date, mode, items } = session;
  const { setNodeRef, hint } = useSessionDrop("session-chip", date, id);
  const spare = items.reduce((n, it) => n + it.portions - it.eaten, 0);
  return (
    <button
      ref={setNodeRef}
      className={`session-chip ${mode}${open ? " open" : ""}${id ? "" : " placeholder"}${hint ? " dragover" : ""}`}
      onClick={onToggle}
      title={open ? "Close" : "Open this session"}
    >
      <span className={`session-dot ${sessionColor(date, monday)}`} />
      <strong>{dayLabel(date)}</strong>
      {!session.in_window && <span className="muted">earlier</span>}
      <span className={`mode-tag ${mode}`}>{mode}</span>
      <span className="muted">
        {hint
          ? "drop to link here"
          : items.length === 0
            ? "empty"
            : `${items.length} recipe${items.length === 1 ? "" : "s"}`}
      </span>
      {!hint && <Spare count={spare} />}
    </button>
  );
}

/** The open session, rolled out over the week table: a comfortable list
 * of everything it covers. Closes on ×, Esc or a click outside; "Details"
 * opens the session's own page. */
function SessionPanel({
  session,
  onClose,
  monday,
  admin,
  onRemoveItem,
  onDelete,
  onOpenDetails,
}: Props & { session: Session; onClose: () => void }) {
  const { id, date, mode } = session;
  // What the rules allow here (the server has the final say).
  const canGrow = admin || mode === "plan";
  const { setNodeRef, hint } = useSessionDrop("session-panel", date, id);
  const panel = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onDown = (e: MouseEvent) => {
      const target = e.target as Element;
      // Clicks on the chips switch or close sessions themselves.
      if (panel.current?.contains(target) || target.closest(".session-strip")) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose]);

  const portions = session.items.reduce((n, it) => n + it.portions, 0);
  return (
    <div
      ref={(node) => {
        panel.current = node;
        setNodeRef(node);
      }}
      className={`session-panel ${mode}${hint ? " dragover" : ""}`}
    >
      <div className="session-head">
        <span className={`session-dot ${sessionColor(date, monday)}`} />
        <strong>{dayLabel(date)}</strong>
        <span className={`mode-tag ${mode}`}>{mode}</span>
        <span className="muted">
          {hint
            ? "drop to link this meal here"
            : `${session.items.length} recipe${session.items.length === 1 ? "" : "s"} · ${portions} portions`}
        </span>
        <span className="session-actions">
          {id && <button onClick={() => onOpenDetails(id)}>Details →</button>}
          {id && (
            <button title="Delete session" onClick={() => onDelete(id)}>
              delete
            </button>
          )}
          <button className="x" title="Close (Esc)" onClick={onClose}>
            ×
          </button>
        </span>
      </div>
      {session.items.length === 0 ? (
        <span className="empty-slot">
          {canGrow ? "nothing yet: drop a meal on this chip to prep it in this session" : "nothing prepped"}
        </span>
      ) : (
        <div className="session-items">
          {session.items.map((it) => (
            <ItemRow key={it.recipe} it={it} session={id} onRemoveItem={onRemoveItem} />
          ))}
        </div>
      )}
    </div>
  );
}

/** One recipe of the open session: batches, portions, the meals it feeds. */
function ItemRow({
  it,
  session,
  onRemoveItem,
}: {
  it: SessionItem;
  session: string | null;
  onRemoveItem: Props["onRemoveItem"];
}) {
  return (
    <div className="session-item">
      {it.card_url ? (
        <a className="item-title" href={it.card_url} target="_blank" rel="noreferrer" title={it.title}>
          {it.title}
        </a>
      ) : (
        <span className="item-title" title={`${it.title} (recipe no longer exists)`}>
          {it.title}
        </span>
      )}
      <span className="item-amount">
        {batchLabel(it.batches)} · {it.portions} portion{it.portions === 1 ? "" : "s"}
      </span>
      <span className="item-meals" title="Meals this recipe feeds">
        {mealsLabel(it.meals) || "no meals"}
      </span>
      <Spare count={it.portions - it.eaten} />
      <button
        className="x"
        title="Remove from session"
        onClick={() => session && onRemoveItem(session, it.recipe)}
      >
        ×
      </button>
    </div>
  );
}
