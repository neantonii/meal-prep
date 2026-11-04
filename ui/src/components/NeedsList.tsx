import { useState } from "react";
import { onHand, type AisleNeeds, type NeededIngredient } from "../api";

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

/** Whole packs to buy (a started pack counts as one); null when the line
 * has no package (frozen before packages were recorded). */
function packsToBuy(it: NeededIngredient): number | null {
  return it.packages === null ? null : Math.max(1, Math.ceil(it.packages - 1e-9));
}

/** What whole packs cost: the line's cost scaled from the packs it uses. */
function buyCost(it: NeededIngredient): number {
  const packs = packsToBuy(it);
  if (packs === null || !it.packages) return it.cost;
  return (it.cost / it.packages) * packs;
}

type View = "all" | "buy";

/** ``needs`` narrowed to the ingredients of the ``picked`` recipes (by
 * title) and, in the to-buy view, to what isn't on hand; aisle counts and
 * costs recomputed. A shared ingredient keeps its whole-session amount. */
function narrow(needs: AisleNeeds[], picked: Set<string>, view: View): AisleNeeds[] {
  return needs
    .map((group) => {
      const ingredients = group.ingredients.filter(
        (it) =>
          (picked.size === 0 || it.recipes.some((r) => picked.has(r))) &&
          (view === "all" || !onHand(it)),
      );
      const cost = ingredients.reduce((n, it) => n + (view === "buy" ? buyCost(it) : it.cost), 0);
      return { ...group, ingredients, cost };
    })
    .filter((group) => group.ingredients.length > 0);
}

/** The to-buy list as plain text, for a note or a message. */
function asText(groups: AisleNeeds[], day: string): string {
  const lines = [`To buy for ${day}`];
  for (const group of groups) {
    lines.push("", aisleLabel(group.aisle));
    for (const it of group.ingredients) {
      const packs = packsToBuy(it);
      const amount = packs === null ? gramsLabel(it.grams) : `${packs} ×`;
      lines.push(`- ${amount} ${it.product ?? it.name}`);
    }
  }
  return lines.join("\n");
}

interface LineProps {
  it: NeededIngredient;
  view: View;
  onHave: (ids: string[], have: boolean) => void;
  onAlways: (id: string, always: boolean) => void;
}

function Line({ it, view, onHave, onAlways }: LineProps) {
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
  const buying = view === "buy";
  const packs = packsToBuy(it);
  const qty = buying
    ? packs === null
      ? gramsLabel(it.grams)
      : String(packs)
    : it.packages !== null
      ? packagesLabel(it.packages)
      : gramsLabel(it.grams);
  return (
    <tr className={`need${onHand(it) ? " on-hand" : ""}`} title={hover}>
      <td className="need-check">
        <input
          type="checkbox"
          checked={onHand(it)}
          disabled={it.always}
          title={it.always ? "Always on hand (untick ∞ to change)" : "I have enough for this session"}
          onChange={(e) => onHave([it.ingredient], e.target.checked)}
        />
      </td>
      <td className="need-qty">{qty}</td>
      <td className="need-name">
        {name}
        <button
          className={`always${it.always ? " on" : ""}`}
          title={
            it.always
              ? "Always on hand, in every session: click to stop"
              : "Always on hand, in every session (oils, spices, sauces)"
          }
          onClick={() => onAlways(it.ingredient, !it.always)}
        >
          ∞
        </button>
        {it.product && <div className="need-meta muted">{it.product}</div>}
      </td>
      <td className="need-size muted">{size ?? "—"}</td>
      <td className="need-cost">${(buying ? buyCost(it) : it.cost).toFixed(2)}</td>
    </tr>
  );
}

interface Props {
  needs: AisleNeeds[];
  day: string;
  picked: Set<string>;
  onShowAll: () => void;
  onHave: (ids: string[], have: boolean) => void;
  onAlways: (id: string, always: boolean) => void;
}

/** What to have on hand by a session, by aisle in walking order, with a
 * checklist: tick what is at home (∞: always, in every session). "To buy"
 * keeps only the rest, in whole packs. Spices start collapsed in the full
 * list (mostly staples), unless recipes are picked. */
export default function NeedsList({ needs, day, picked, onShowAll, onHave, onAlways }: Props) {
  const [view, setView] = useState<View>("all");
  const [copied, setCopied] = useState(false);
  const shown = narrow(needs, picked, view);
  const total = shown.reduce((n, g) => n + g.cost, 0);
  const toBuy = narrow(needs, picked, "buy").reduce((n, g) => n + g.ingredients.length, 0);
  const filtered = picked.size > 0;
  const copy = () => {
    void navigator.clipboard.writeText(asText(shown, day)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <aside className="needs">
      <h3>
        Needed by {day} <span className="muted">${total.toFixed(2)}</span>
      </h3>
      <div className="needs-views">
        <button className={view === "all" ? "on" : ""} onClick={() => setView("all")}>
          All
        </button>
        <button className={view === "buy" ? "on" : ""} onClick={() => setView("buy")}>
          To buy ({toBuy})
        </button>
        {view === "buy" && shown.length > 0 && (
          <button onClick={copy}>{copied ? "copied" : "copy as text"}</button>
        )}
      </div>
      {filtered ? (
        <p className="needs-filter">
          <span className="muted">
            For {[...picked].join(", ")} (amounts are for the whole session)
          </span>
          <button onClick={onShowAll}>show all</button>
        </p>
      ) : (
        <p className="muted needs-note">
          {view === "buy"
            ? "What isn't ticked, in whole packs. Tick what you have in the All view."
            : "Tick what you have; ∞ marks it on hand in every session. Click recipes on the left to show only theirs."}
        </p>
      )}
      {shown.length === 0 && (
        <p className="muted">{view === "buy" ? "Nothing to buy." : "Nothing yet."}</p>
      )}
      {shown.map((group) => (
        <details
          key={`${group.aisle ?? "none"}:${filtered}:${view}`}
          className="aisle"
          open={filtered || view === "buy" || group.aisle !== "spices"}
        >
          <summary>
            <strong>{aisleLabel(group.aisle)}</strong>
            <span className="muted">
              {group.ingredients.length} · ${group.cost.toFixed(2)}
            </span>
          </summary>
          <table className="needs-table">
            <thead>
              <tr>
                <th className="need-check" />
                <th className="need-qty">Packs</th>
                <th>Ingredient</th>
                <th className="need-size">Pack size</th>
                <th className="need-cost">Cost</th>
              </tr>
            </thead>
            <tbody>
              {group.ingredients.map((it) => (
                <Line
                  key={`${it.ingredient}:${it.product ?? ""}`}
                  it={it}
                  view={view}
                  onHave={onHave}
                  onAlways={onAlways}
                />
              ))}
            </tbody>
          </table>
        </details>
      ))}
    </aside>
  );
}
