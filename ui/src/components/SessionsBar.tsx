import { useDndContext, useDraggable, useDroppable } from "@dnd-kit/core";
import { useEffect, useRef, useState } from "react";
import type { Session, SessionItem } from "../api";
import { dayLabel, mealsLabel, sessionColor, spareOf } from "../api";
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
  /** Remove one batch of a recipe (its portions come out of Unassigned). */
  onRemoveBatch: (session: string, recipe: string) => void;
  /** Open the session's own page. */
  onOpenDetails: (session: string) => void;
}

/** A session as a drop target (its chip or open panel): a recipe line
 * dragged from another session moves here with all its meals; an empty
 * placeholder day gets its session created. `hint` is true while such a
 * line hovers. The drop itself is handled in App's onDragEnd. */
function useSessionDrop(where: string, date: string, session: string | null) {
  const { setNodeRef, isOver } = useDroppable({
    id: `${where}:${date}`,
    data: { kind: "session", date, session } satisfies DropData,
  });
  const { active } = useDndContext();
  const from = active?.data.current as DragData | undefined;
  const hint = isOver && from?.kind === "item" && from.session !== session;
  return { setNodeRef, hint };
}

function batchLabel(batches: number): string {
  return `${batches} batch${batches === 1 ? "" : "es"}`;
}

/** Portions no meal accounts for. Every portion is a meal (on a day,
 * unassigned or binned), so this only shows when something went wrong: an
 * interrupted edit, a hand-edited file, or a session from before portions
 * were meals. */
function Spare({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span
      className="spare"
      title={`${count} portion${count === 1 ? "" : "s"} no meal accounts for: something went wrong`}
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
  const spare = items.reduce((n, it) => n + Math.max(0, spareOf(it)), 0);
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
          ? "drop to cook it here"
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
  today,
  monday,
  admin,
  onRemoveBatch,
  onOpenDetails,
}: Props & { session: Session; onClose: () => void }) {
  const { id, date, mode } = session;
  // What the rules allow here (the server has the final say): today's
  // session is still planned, as the prep happens during its day.
  const planned = admin || mode === "plan" || date === today;
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
            ? "drop to cook this recipe in this session"
            : `${session.items.length} recipe${session.items.length === 1 ? "" : "s"} · ${portions} portions`}
        </span>
        <span className="session-actions">
          {id && <button onClick={() => onOpenDetails(id)}>Details →</button>}
          <button className="x" title="Close (Esc)" onClick={onClose}>
            ×
          </button>
        </span>
      </div>
      {session.items.length === 0 ? (
        <span className="empty-slot">
          {planned
            ? "nothing yet: a recipe dropped on a day lands in its cycle's session; drag a recipe row here from another session to cook it on this day"
            : "nothing prepped"}
        </span>
      ) : (
        <div className="session-items">
          {byCategory(session.items).map(([category, items]) => (
            <div className="session-group" key={category ?? "other"}>
              <div className="session-group-title">
                {items[0].category_label ?? "other (recipe removed)"}
              </div>
              {items.map((it) => (
                <ItemRow
                  key={it.recipe}
                  it={it}
                  session={id}
                  planned={planned}
                  onRemoveBatch={onRemoveBatch}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Items grouped by category; the server already lists them in category
 * order, so a group is a run of items sharing one. */
function byCategory(items: SessionItem[]): [string | null, SessionItem[]][] {
  const groups: [string | null, SessionItem[]][] = [];
  for (const it of items) {
    const last = groups[groups.length - 1];
    if (last && last[0] === it.category) last[1].push(it);
    else groups.push([it.category, [it]]);
  }
  return groups;
}

/** Where the portions that are on no day are: "2 unassigned · 1 binned". */
function elsewhere(it: SessionItem): string {
  return [it.unassigned > 0 && `${it.unassigned} unassigned`, it.binned > 0 && `${it.binned} binned`]
    .filter(Boolean)
    .join(" · ");
}

/** One recipe of the open session: batches, portions and where they are.
 * Its title is a handle: drag it onto a day to cook one more batch here,
 * or onto another session to move the whole line there. */
function ItemRow({
  it,
  session,
  planned,
  onRemoveBatch,
}: {
  it: SessionItem;
  session: string | null;
  planned: boolean;
  onRemoveBatch: Props["onRemoveBatch"];
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `item:${session}:${it.recipe}`,
    disabled: session === null,
    data: {
      kind: "item",
      session: session ?? "",
      recipe: it.recipe,
      title: it.title,
    } satisfies DragData,
  });
  const meals = [mealsLabel(it.meals), elsewhere(it)].filter(Boolean).join(" · ");
  return (
    <div className={`session-item${isDragging ? " dragging" : ""}`}>
      <span
        ref={setNodeRef}
        className="item-handle"
        title="Drag to a day to cook one more batch here, or to another session to move this recipe there"
        {...attributes}
        {...listeners}
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
      </span>
      <span className="item-amount">
        {batchLabel(it.batches)} · {it.portions} portion{it.portions === 1 ? "" : "s"}
      </span>
      <span className="item-meals" title="Where this recipe's portions are">
        {meals || "no meals"}
      </span>
      <Spare count={spareOf(it)} />
      <button
        className="x"
        disabled={!planned}
        title={
          planned
            ? "Remove one batch: its portions must be unassigned first"
            : "Already cooked: Admin can remove a batch"
        }
        onClick={() => session && onRemoveBatch(session, it.recipe)}
      >
        − batch
      </button>
    </div>
  );
}
