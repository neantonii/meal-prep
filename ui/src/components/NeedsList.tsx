import type { AisleNeeds, NeededIngredient } from "../api";

/** "1.4", "2", or "< 0.1" for a pinch. */
function packagesLabel(n: number): string {
  if (n < 0.05) return "< 0.1";
  return String(Math.round(n * 10) / 10);
}

/** The package size as authored, with 1000 g / ml shown as kg / l. */
function sizeLabel(amount: number, unit: string): string {
  const big = { g: "kg", ml: "l" }[unit];
  if (big && amount >= 1000) return `${Number((amount / 1000).toFixed(2))} ${big}`;
  const n = Number(amount.toFixed(2));
  return unit === "count" ? `${n} pcs` : `${n} ${unit}`;
}

function gramsLabel(g: number): string {
  return g >= 1000 ? `${(g / 1000).toFixed(2)} kg` : `${Math.round(g)} g`;
}

function aisleLabel(aisle: string | null): string {
  return aisle ? aisle.charAt(0).toUpperCase() + aisle.slice(1) : "Not recorded";
}

function Line({ it }: { it: NeededIngredient }) {
  const name = it.card_url ? (
    <a href={it.card_url} target="_blank" rel="noreferrer">
      {it.name}
    </a>
  ) : (
    it.name
  );
  const size =
    it.package_amount !== null && it.package_unit
      ? sizeLabel(it.package_amount, it.package_unit)
      : null;
  // Hover spells the amount out, for when the product title is unclear or
  // the size column is hidden on a narrow panel.
  const hover = [
    it.packages !== null && size ? `${packagesLabel(it.packages)} × ${size} pack` : null,
    `${gramsLabel(it.grams)} used`,
    `for ${it.recipes.join(", ")}`,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <tr className="need" title={hover}>
      <td className="need-qty">
        {it.packages !== null ? packagesLabel(it.packages) : gramsLabel(it.grams)}
      </td>
      <td className="need-name">
        {name}
        {it.product && <div className="need-meta muted">{it.product}</div>}
      </td>
      <td className="need-size muted">{size ?? "—"}</td>
      <td className="need-cost">${it.cost.toFixed(2)}</td>
    </tr>
  );
}

/** What to have on hand by a session, by aisle in walking order. Not a
 * purchase list: what is already at home isn't subtracted. Spices start
 * collapsed (mostly staples). */
export default function NeedsList({ needs, day }: { needs: AisleNeeds[]; day: string }) {
  const total = needs.reduce((n, g) => n + g.cost, 0);
  return (
    <aside className="needs">
      <h3>
        Needed by {day} <span className="muted">${total.toFixed(2)}</span>
      </h3>
      <p className="muted needs-note">
        Everything the session's batches use, in packs (hover a line for its pack size and
        grams). What's already at home isn't subtracted.
      </p>
      {needs.length === 0 && <p className="muted">Nothing yet.</p>}
      {needs.map((group) => (
        <details key={group.aisle ?? "none"} className="aisle" open={group.aisle !== "spices"}>
          <summary>
            <strong>{aisleLabel(group.aisle)}</strong>
            <span className="muted">
              {group.ingredients.length} · ${group.cost.toFixed(2)}
            </span>
          </summary>
          <table className="needs-table">
            <thead>
              <tr>
                <th className="need-qty">Packs</th>
                <th>Ingredient</th>
                <th className="need-size">Pack size</th>
                <th className="need-cost">Cost</th>
              </tr>
            </thead>
            <tbody>
              {group.ingredients.map((it) => (
                <Line key={`${it.ingredient}:${it.product ?? ""}`} it={it} />
              ))}
            </tbody>
          </table>
        </details>
      ))}
    </aside>
  );
}
