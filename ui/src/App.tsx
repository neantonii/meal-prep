import { useCallback, useEffect, useRef, useState } from "react";
import { api, sessionColor, shiftWeek, type CatalogGroup, type DiaryWeek, type Link, type Placement } from "./api";
import Palette from "./components/Palette";
import SessionsBar from "./components/SessionsBar";
import WeekGrid from "./components/WeekGrid";

function weekFromUrl(): string | null {
  const w = new URLSearchParams(window.location.search).get("week");
  return w && /^\d{4}-W\d{2}$/.test(w) ? w : null;
}

export default function App() {
  const [week, setWeek] = useState<string | null>(weekFromUrl());
  const [groups, setGroups] = useState<CatalogGroup[]>([]);
  const [state, setState] = useState<DiaryWeek | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState<string>("");
  // Admin mode amends history; deliberately not remembered across reloads.
  const [admin, setAdmin] = useState(false);
  // Placeholder sessions added with "+ session", per week; saved once they
  // get a recipe.
  const [extraDates, setExtraDates] = useState<Record<string, string[]>>({});
  // Entry changes run one at a time, in the order they were made.
  const queue = useRef<Promise<void>>(Promise.resolve());

  const openWeek = useCallback(async (w: string, push = false) => {
    setError(null);
    try {
      const data = await api.diary(w);
      setState(data);
      setWeek(w);
      if (push) window.history.pushState(null, "", `/?week=${w}`);
      else window.history.replaceState(null, "", `/?week=${w}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  // Product version for the header, e.g. "v0.0.3 · efc0cfe" (just "dev" locally).
  useEffect(() => {
    api
      .version()
      .then((v) =>
        setVersion(
          v.version === "dev"
            ? "dev"
            : `v${v.version} · ${v.commit.slice(0, 7)}`,
        ),
      )
      .catch(() => setVersion(""));
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [cat, w] = await Promise.all([
          api.catalog(),
          week ? { week } : api.currentWeek(),
        ]);
        setGroups(cat.groups);
        await openWeek(w.week);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Browser back/forward: reload the week from the URL.
  useEffect(() => {
    const onPop = () => {
      const w = weekFromUrl();
      if (w) void openWeek(w);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [openWeek]);

  /** Run one entry change on the server and show the week it returns. */
  const change = (op: (week: string) => Promise<DiaryWeek>) => {
    if (!state) return;
    const week = state.week;
    queue.current = queue.current.then(async () => {
      setSaving(true);
      setError(null);
      try {
        const next = await op(week);
        setState((cur) => (cur?.week === week ? next : cur));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setSaving(false);
      }
    });
  };

  const handleAdd = (recipe: string, where: Placement, session: Link) =>
    change((w) => api.addEntry(w, recipe, where, session, admin));
  const handleRemove = (id: string) => change((w) => api.removeEntry(w, id, admin));
  const handleMove = (id: string, where: Placement) =>
    change((w) => api.moveEntry(w, id, where, admin));
  const handleLink = (id: string, session: string | null) =>
    change((w) => api.linkEntry(w, id, session, admin));

  // Session id -> color class (from its date), for chips and entry edges.
  const colors: Record<string, string> = {};
  const monday = state?.days[0]?.date ?? "";
  for (const s of state?.sessions ?? []) if (s.id) colors[s.id] = sessionColor(s.date, monday);

  const switchWeek = (delta: number) => {
    if (!state) return;
    void openWeek(shiftWeek(state.week, delta), true);
  };

  const totals = state?.totals ?? {};
  const dates = state?.days.map((d) => d.date) ?? [];

  return (
    <>
      <header className="top">
        <div className="pager">
          <button title="Previous week" onClick={() => switchWeek(-1)}>
            ‹
          </button>
          <strong>{state?.week ?? "…"}</strong>
          <button title="Next week" onClick={() => switchWeek(1)}>
            ›
          </button>
        </div>
        <h1>Diary</h1>
        <div className="actions" style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {version && <span className="version">{version}</span>}
          <button
            className={admin ? "admin-on" : ""}
            title="Admin mode: amend history (rules still apply, nothing is auto-filled)"
            onClick={() => setAdmin((a) => !a)}
          >
            {admin ? "Admin on" : "Admin"}
          </button>
          {saving ? (
            <span className="dirty">saving…</span>
          ) : (
            <span className="saved">✓ saved</span>
          )}
        </div>
      </header>
      {admin && (
        <div className="admin-banner">
          Admin mode: you are amending history. Rules still apply; nothing is auto-filled.
        </div>
      )}
      {error && <div className="err">{error}</div>}
      <main className="layout">
        <section>
          <div className="week-head">
            <span>
              {dates.length > 0 ? `${dates[0]} – ${dates[dates.length - 1]}` : ""}
            </span>
            <span className="totals">
              {state?.exists
                ? `${Math.round(totals["kcal"] ?? 0)} kcal · ${Math.round(totals["protein_g"] ?? 0)}g P · $${(totals["cost"] ?? 0).toFixed(2)}`
                : state
                  ? "nothing logged yet"
                  : ""}
            </span>
          </div>
          {state && (
            <SessionsBar
              sessions={state.sessions}
              today={state.today}
              monday={state.days[0]?.date ?? ""}
              extraDates={extraDates[state.week] ?? []}
              admin={admin}
              onAddDate={(date) =>
                setExtraDates((cur) => ({
                  ...cur,
                  [state.week]: [...(cur[state.week] ?? []), date],
                }))
              }
              onAddItem={(date, recipe) => change((w) => api.addItem(w, date, recipe, admin))}
              onUpdateItem={(session, recipe, batches) =>
                change((w) => api.updateItem(w, session, recipe, batches, admin))
              }
              onRemoveItem={(session, recipe) =>
                change((w) => api.removeItem(w, session, recipe, admin))
              }
              onDelete={(session) => change((w) => api.deleteSession(w, session, admin))}
              onLinkEntry={handleLink}
            />
          )}
          {state && (
            <WeekGrid
              days={state.days}
              sessions={state.sessions}
              colors={colors}
              monday={state.days[0]?.date ?? ""}
              onAdd={handleAdd}
              onRemove={handleRemove}
              onMove={handleMove}
            />
          )}
        </section>
        <Palette groups={groups} />
      </main>
    </>
  );
}
