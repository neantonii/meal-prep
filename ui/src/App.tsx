import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  MEALTIMES,
  api,
  shiftWeek,
  type CatalogEntry,
  type CatalogGroup,
  type DiaryWeek,
  type Mealtime,
} from "./api";
import Palette from "./components/Palette";
import WeekGrid, { type MoveRef } from "./components/WeekGrid";

function weekFromUrl(): string | null {
  const w = new URLSearchParams(window.location.search).get("week");
  return w && /^\d{4}-W\d{2}$/.test(w) ? w : null;
}

function toPayload(week: DiaryWeek) {
  return {
    week: week.week,
    days: week.days.flatMap((d) => {
      const meals = d.meals.filter((m) => m.recipes.length > 0);
      if (meals.length === 0) return [];
      const o: Record<string, string[] | string> = { date: d.date };
      for (const m of meals) o[m.mealtime] = m.recipes;
      return [o];
    }),
  };
}

export default function App() {
  const [week, setWeek] = useState<string | null>(weekFromUrl());
  const [groups, setGroups] = useState<CatalogGroup[]>([]);
  const [state, setState] = useState<DiaryWeek | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const byId = useMemo(() => {
    const m = new Map<string, CatalogEntry>();
    for (const g of groups) for (const r of g.recipes) m.set(r.id, r);
    return m;
  }, [groups]);

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

  const persist = useCallback(
    async (next: DiaryWeek) => {
      setSaving(true);
      setError(null);
      try {
        const nonEmpty = next.days.some((d) =>
          MEALTIMES.some((m) =>
            d.meals.some((x) => x.mealtime === m && x.recipes.length > 0),
          ),
        );
        if (!nonEmpty) {
          await api.deleteDiary(next.week);
          const fresh = await api.diary(next.week);
          setState(fresh);
        } else {
          const saved = await api.saveDiary(next.week, toPayload(next));
          setState(saved);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setSaving(false);
      }
    },
    [],
  );

  // Debounced autosave: every change hits the server ~600ms after the last edit.
  useEffect(
    () => () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    },
    [],
  );

  const mutate = (fn: (days: DiaryWeek["days"]) => void) => {
    if (!state) return;
    const days = state.days.map((d) => ({
      ...d,
      meals: d.meals.map((m) => ({ ...m, recipes: [...m.recipes] })),
    }));
    fn(days);
    const next = { ...state, days };
    setState(next);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => void persist(next), 600);
  };

  const mealOf = (dayIdx: number, meal: Mealtime, days: DiaryWeek["days"]) => {
    let m = days[dayIdx].meals.find((x) => x.mealtime === meal);
    if (!m) {
      m = { mealtime: meal, recipes: [] };
      days[dayIdx].meals.push(m);
    }
    return m;
  };

  const handleAdd = (day: number, meal: Mealtime, id: string) =>
    mutate((days) => {
      mealOf(day, meal, days).recipes.push(id);
    });

  const handleRemove = (day: number, meal: Mealtime, idx: number) =>
    mutate((days) => {
      const m = days[day].meals.find((x) => x.mealtime === meal);
      if (!m) return;
      m.recipes.splice(idx, 1);
      if (m.recipes.length === 0)
        days[day].meals = days[day].meals.filter((x) => x !== m);
    });

  const handleMove = (from: MoveRef, toDay: number, toMeal: Mealtime) =>
    mutate((days) => {
      const src = days[from.day].meals.find((x) => x.mealtime === from.meal);
      if (!src) return;
      const [id] = src.recipes.splice(from.idx, 1);
      if (id === undefined) return;
      if (src.recipes.length === 0)
        days[from.day].meals = days[from.day].meals.filter((x) => x !== src);
      mealOf(toDay, toMeal, days).recipes.push(id);
    });

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
          {saving ? (
            <span className="dirty">saving…</span>
          ) : (
            <span className="saved">✓ saved</span>
          )}
        </div>
      </header>
      {error && <div className="err">{error}</div>}
      <main className="layout">
        <section>
          <div className="week-head">
            <span>
              {dates.length > 0 ? `${dates[0]} – ${dates[dates.length - 1]}` : ""}
            </span>
            <span className="totals">
              {totals["kcal"] != null
                ? `${Math.round(totals["kcal"])} kcal · ${Math.round(totals["protein_g"] ?? 0)}g P · $${(totals["cost"] ?? 0).toFixed(2)}`
                : state
                  ? "unsaved week"
                  : ""}
            </span>
          </div>
          {state && (
            <WeekGrid
              days={state.days}
              byId={byId}
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
