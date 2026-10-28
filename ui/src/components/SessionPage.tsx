import { useEffect, useState } from "react";
import { api, dayLabel, mealsLabel, type SessionDetail } from "../api";

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
 * (batches, portions, the meals it feeds). Ingredient totals come later. */
export default function SessionPage({ id, fromWeek, onBack }: Props) {
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .session(id)
      .then(setDetail)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, [id]);

  if (error) return <div className="err">{error}</div>;
  if (!detail) return <div className="session-page muted">loading…</div>;
  const { session, totals } = detail;
  const week = fromWeek ?? detail.week;

  return (
    <main className="session-page">
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
            </tr>
          </thead>
          <tbody>
            {session.items.map((it) => {
              const spare = it.portions - it.eaten;
              return (
                <tr key={it.recipe}>
                  <td>
                    {it.card_url ? (
                      <a href={it.card_url} target="_blank" rel="noreferrer">
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
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
