import type { Explanation } from "../api";
import { dayLabel } from "../api";

/** Where a bill line applies, in words: a meal, a day or a session. */
function place(line: Explanation["lines"][number]): string {
  if (line.date && line.mealtime) return `${dayLabel(line.date).split(" ")[0]} ${line.mealtime}`;
  if (line.date) return dayLabel(line.date);
  if (line.session) return `${dayLabel(line.session)} session`;
  return "";
}

const SHOWN = 8;

/** The week ahead's bill (docs/planner.md): total, points per term, the
 * biggest lines, and any broken hard rule. */
export function BillPanel({ bill }: { bill: Explanation }) {
  const lines = bill.lines;
  return (
    <div className="bill">
      <div className="bill-head">
        <strong>Week ahead · {bill.total} pts</strong>
        <span className="muted">
          {dayLabel(bill.start)} – {dayLabel(bill.end)}, your meals and the planner's alike
        </span>
      </div>
      {bill.problems.length > 0 && (
        <ul className="bill-problems">
          {bill.problems.map((p) => (
            <li key={p}>⚠ {p}</li>
          ))}
        </ul>
      )}
      <div className="bill-terms">
        {bill.terms.map((t) => (
          <span key={t.name} className={`bill-term${t.points > 0 ? " cost" : ""}`}>
            {t.name} <b>{t.points}</b>
          </span>
        ))}
      </div>
      {lines.length === 0 ? (
        <p className="muted">Nothing costs points: every meal fits its archetype.</p>
      ) : (
        <ol className="bill-lines">
          {lines.slice(0, SHOWN).map((l, i) => (
            <li key={`${l.term}-${l.reason}-${place(l)}-${i}`}>
              <span className="bill-place">{place(l)}</span>
              <span className="bill-reason">{l.reason}</span>
              <span className="bill-pts">{l.points}</span>
            </li>
          ))}
          {lines.length > SHOWN && <li className="muted">and {lines.length - SHOWN} smaller lines</li>}
        </ol>
      )}
    </div>
  );
}
