import { useEffect, useState } from "react";
import {
  api,
  dayLabel,
  mealsLabel,
  type NeededIngredient,
  type ShareRef,
  type SessionDetail,
} from "../api";
import NeedsList from "./NeedsList";

interface Props {
  id: string;
  /** The week page we came from, if known; else the session's own week. */
  fromWeek: string | null;
  /** Back to the week page, e.g. "2026-W44". */
  onBack: (week: string) => void;
}

function batchLabel(batches: number): string {
  return `${batches} batch${batches === 1 ? "" : "es"}`;
}

/** A prep session's own page: header with totals and one row per recipe
 * (batches, portions, the meals it feeds) on the left; what to have on hand
 * by the session on the right. */
export default function SessionPage({ id, fromWeek, onBack }: Props) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Recipes picked on the left (by title): the needs list shows only theirs.
  const [picked, setPicked] = useState<Set<string>>(new Set());
  // A click picks only that recipe (again: none); ⌘/Ctrl-click adds or
  // removes it, to see several recipes' ingredients together.
  const pick = (title: string, add: boolean) =>
    setPicked((prev) => {
      if (!add) return prev.size === 1 && prev.has(title) ? new Set() : new Set([title]);
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });

  useEffect(() => {
    api
      .session(id)
      .then(setDetail)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  // Checklist edits answer with the refreshed page.
  const run = (call: Promise<SessionDetail>) =>
    call.then(setDetail).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  const onHave = (shares: ShareRef[], have: boolean) => run(api.setHave(id, shares, have));
  const onAlways = (ingredient: string, always: boolean) =>
    run(api.setAlways(id, ingredient, always));

  if (!detail) {
    return error ? <div className="err">{error}</div> : <div className="session-page muted">loading…</div>;
  }
  const { session, totals } = detail;
  const lines: NeededIngredient[] = detail.needs.flatMap((g) => g.ingredients);
  // A recipe's own part of the checklist: its share of each ingredient it
  // uses, on hand when ticked for it or a staple.
  const sharesOf = (recipe: string) =>
    lines.flatMap((l) =>
      l.shares
        .filter((s) => s.recipe === recipe)
        .map((s) => ({ ref: { recipe, ingredient: l.ingredient }, have: s.have, always: l.always })),
    );
  const week = fromWeek ?? detail.week;

  return (
    <main className="session-page">
      <div className="session-main">
        {error && <div className="err">{error}</div>}
        <button className="back" onClick={() => onBack(week)}>
          ← Week {week}
        </button>
        <h2>
          Prep session · {dayLabel(session.date)}{" "}
          <span className={`mode-tag ${session.mode}`}>{session.mode}</span>
        </h2>
        <div className="session-totals">
          <span>
            <strong>{session.items.length}</strong> recipes
          </span>
          <span>
            <strong>{totals["portions"] ?? 0}</strong> portions
          </span>
          <span>
            <strong>${(totals["cost"] ?? 0).toFixed(2)}</strong>
          </span>
          <span>
            <strong>{Math.round(totals["kcal"] ?? 0)}</strong> kcal
          </span>
          <span>
            <strong>{Math.round(totals["protein_g"] ?? 0)}</strong> g protein
          </span>
        </div>
        {session.items.length === 0 ? (
          <p className="muted">Nothing in this session.</p>
        ) : (
          <table className="session-table">
            <thead>
              <tr>
                <th>Recipe</th>
                <th>Batches</th>
                <th>Portions</th>
                <th>Meals</th>
                <th>Cost</th>
                <th>kcal / serving</th>
                <th title="Ingredients on hand (ticked, or always)">Have</th>
              </tr>
            </thead>
            <tbody>
              {session.items.map((it) => {
                const spare = it.portions - it.eaten;
                const own = sharesOf(it.recipe);
                const missing = own.filter((s) => !s.have && !s.always);
                const ticked = own.filter((s) => s.have);
                return (
                  <tr
                    key={it.recipe}
                    className={picked.has(it.title) ? "picked" : undefined}
                    title="Click to show only this recipe's ingredients (⌘/Ctrl-click to add more)"
                    onClick={(e) => pick(it.title, e.metaKey || e.ctrlKey)}
                  >
                    <td>
                      {it.card_url ? (
                        <a
                          href={it.card_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {it.title}
                        </a>
                      ) : (
                        it.title
                      )}
                    </td>
                    <td>{batchLabel(it.batches)}</td>
                    <td>
                      {it.portions}
                      {spare > 0 && <span className="spare"> ⚠ {spare} spare</span>}
                    </td>
                    <td className="meals">{mealsLabel(it.meals) || "—"}</td>
                    <td>${(it.portions * it.cost).toFixed(2)}</td>
                    <td>{Math.round(it.kcal)}</td>
                    <td className="have">
                      {missing.length === 0 ? (
                        <button
                          className="have-done"
                          disabled={ticked.length === 0}
                          title={
                            ticked.length === 0
                              ? "Everything on hand (all staples)"
                              : "Everything on hand: click to untick this recipe's share"
                          }
                          onClick={(e) => {
                            e.stopPropagation();
                            onHave(
                              ticked.map((s) => s.ref),
                              false,
                            );
                          }}
                        >
                          ✓
                        </button>
                      ) : (
                        <>
                          <span className="muted">
                            {own.length - missing.length}/{own.length}
                          </span>{" "}
                          <button
                            title="Tick this recipe's share of every ingredient as on hand"
                            onClick={(e) => {
                              e.stopPropagation();
                              onHave(
                                missing.map((s) => s.ref),
                                true,
                              );
                            }}
                          >
                            have all
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <NeedsList
        needs={detail.needs}
        day={dayLabel(session.date)}
        picked={picked}
        onShowAll={() => setPicked(new Set())}
        onHave={onHave}
        onAlways={onAlways}
      />
    </main>
  );
}
