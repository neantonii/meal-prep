import { useEffect, useRef, useState } from "react";
import {
  missingShares,
  onHand,
  type AisleNeeds,
  type NeededIngredient,
  type NeedShare,
  type ShareRef,
} from "../api";

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

type View = "all" | "buy";

/** What a line still needs bought: the unticked shares (of the picked
 * recipes, when some are picked), in whole packs. ``packs`` is null when
 * the line has no package (frozen before packages were recorded). */
interface ToBuy {
  shares: NeedShare[];
  packs: number | null;
  grams: number;
  cost: number;
}

function toBuy(it: NeededIngredient, picked: Set<string>): ToBuy {
  const shares = missingShares(it).filter((s) => picked.size === 0 || picked.has(s.title));
  const grams = shares.reduce((n, s) => n + s.grams, 0);
  const packages = shares.reduce((n, s) => n + (s.packages ?? 0), 0);
  if (it.packages === null || !it.packages || shares.some((s) => s.packages === null)) {
    return { shares, packs: null, grams, cost: shares.reduce((n, s) => n + s.cost, 0) };
  }
  // A started pack counts as one; its cost scales from what the line uses.
  const packs = Math.max(1, Math.ceil(packages - 1e-9));
  return { shares, packs, grams, cost: (it.cost / it.packages) * packs };
}

/** ``needs`` narrowed to the ingredients of the ``picked`` recipes (by
 * title) and, in the to-buy view, to what still needs buying; aisle counts
 * and costs recomputed. In the full view a shared ingredient keeps its
 * whole-session amount. */
function narrow(needs: AisleNeeds[], picked: Set<string>, view: View): AisleNeeds[] {
  return needs
    .map((group) => {
      const ingredients = group.ingredients.filter((it) =>
        view === "buy"
          ? toBuy(it, picked).shares.length > 0
          : picked.size === 0 || it.recipes.some((r) => picked.has(r)),
      );
      const cost = ingredients.reduce(
        (n, it) => n + (view === "buy" ? toBuy(it, picked).cost : it.cost),
        0,
      );
      return { ...group, ingredients, cost };
    })
    .filter((group) => group.ingredients.length > 0);
}

/** The to-buy list as plain text, for a note or a message. */
function asText(groups: AisleNeeds[], picked: Set<string>, day: string): string {
  const lines = [`To buy for ${day}`];
  for (const group of groups) {
    lines.push("", aisleLabel(group.aisle));
    for (const it of group.ingredients) {
      const buy = toBuy(it, picked);
      const amount = buy.packs === null ? gramsLabel(buy.grams) : `${buy.packs} ×`;
      lines.push(`- ${amount} ${it.product ?? it.name}`);
    }
  }
  return lines.join("\n");
}

/** Put ``text`` on the clipboard; ``true`` when it worked. The clipboard
 * API exists only on HTTPS or localhost, so over plain http (a home-network
 * address) fall back to the older copy command. */
async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // refused (permissions, focus): try the fallback
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

/** A checkbox that can also show "partly" (some recipes' shares ticked). */
function Tick(props: {
  checked: boolean;
  partly: boolean;
  disabled: boolean;
  title: string;
  onChange: (checked: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = props.partly;
  }, [props.partly]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={props.checked}
      disabled={props.disabled}
      title={props.title}
      onChange={(e) => props.onChange(e.target.checked)}
    />
  );
}

interface LineProps {
  it: NeededIngredient;
  view: View;
  picked: Set<string>;
  onHave: (shares: ShareRef[], have: boolean) => void;
  onAlways: (id: string, always: boolean) => void;
}

function Line({ it, view, picked, onHave, onAlways }: LineProps) {
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
  // Hover spells the amount out, recipe by recipe, with their ticks.
  const amount = (s: { packages: number | null; grams: number }) =>
    s.packages !== null ? `${packagesLabel(s.packages)} pack` : gramsLabel(s.grams);
  const hover = [
    it.packages !== null && size ? `${packagesLabel(it.packages)} × ${size} pack` : null,
    `${gramsLabel(it.grams)} used`,
    ...it.shares.map((s) => `${s.title}: ${amount(s)}${s.have ? " ✓" : ""}`),
  ]
    .filter(Boolean)
    .join("\n");
  const buy = view === "buy" ? toBuy(it, picked) : null;
  const qty = buy
    ? buy.packs === null
      ? gramsLabel(buy.grams)
      : String(buy.packs)
    : it.packages !== null
      ? packagesLabel(it.packages)
      : gramsLabel(it.grams);
  const ticked = it.shares.filter((s) => s.have).length;
  const refs = it.shares.map((s) => ({ recipe: s.recipe, ingredient: it.ingredient }));
  return (
    <tr className={`need${onHand(it) ? " on-hand" : ""}`} title={hover}>
      <td className="need-check">
        <Tick
          checked={onHand(it)}
          partly={!it.always && ticked > 0 && ticked < it.shares.length}
          disabled={it.always}
          title={
            it.always
              ? "Always on hand (turn off ∞ to change)"
              : "I have enough for every recipe that uses it"
          }
          onChange={(checked) => onHave(refs, checked)}
        />
      </td>
      <td className="need-always">
        <button
          className={`always${it.always ? " on" : ""}`}
          title={
            it.always
              ? "Always on hand, in every session: click to turn off"
              : "Always on hand, in every session (oils, spices, sauces)"
          }
          onClick={() => onAlways(it.ingredient, !it.always)}
        >
          ∞
        </button>
      </td>
      <td className="need-qty">{qty}</td>
      <td className="need-name">
        {name}
        {it.product && <div className="need-meta muted">{it.product}</div>}
      </td>
      <td className="need-size muted">{size ?? "—"}</td>
      <td className="need-cost">${(buy ? buy.cost : it.cost).toFixed(2)}</td>
    </tr>
  );
}

interface Props {
  needs: AisleNeeds[];
  day: string;
  picked: Set<string>;
  onShowAll: () => void;
  onHave: (shares: ShareRef[], have: boolean) => void;
  onAlways: (id: string, always: boolean) => void;
}

/** What to have on hand by a session, by aisle in walking order, with a
 * checklist: tick what is at home (a line: enough for every recipe using
 * it; ∞: always, in every session). "To buy" keeps the rest, in whole
 * packs. Spices start collapsed in the full list (mostly staples), unless
 * recipes are picked. */
export default function NeedsList({ needs, day, picked, onShowAll, onHave, onAlways }: Props) {
  const [view, setView] = useState<View>("all");
  const [copied, setCopied] = useState(false);
  // Shown when copying failed: the list, selected, to copy by hand.
  const [manual, setManual] = useState<string | null>(null);
  const shown = narrow(needs, picked, view);
  const total = shown.reduce((n, g) => n + g.cost, 0);
  const toBuyCount = narrow(needs, picked, "buy").reduce((n, g) => n + g.ingredients.length, 0);
  const filtered = picked.size > 0;
  const copy = () => {
    const text = asText(shown, picked, day);
    void copyText(text).then((ok) => {
      if (!ok) {
        setManual(text);
        return;
      }
      setManual(null);
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
          To buy ({toBuyCount})
        </button>
        {view === "buy" && shown.length > 0 && (
          <button onClick={copy}>{copied ? "copied" : "copy as text"}</button>
        )}
      </div>
      {manual !== null && (
        <div className="copy-manual">
          <p className="muted">
            Couldn't copy automatically here: the list is selected below, copy it with
            ⌘C / Ctrl+C (or long-press on a phone).
            <button onClick={() => setManual(null)}>close</button>
          </p>
          <textarea
            readOnly
            value={manual}
            rows={Math.min(12, manual.split("\n").length)}
            ref={(el) => el?.select()}
          />
        </div>
      )}
      {filtered ? (
        <p className="needs-filter">
          <span className="muted">
            For {[...picked].join(", ")}
            {view === "all" ? " (amounts are for the whole session)" : " (their shares only)"}
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
                <th className="need-check" title="On hand for this session" />
                <th className="need-always" title="Always on hand, in every session">
                  ∞
                </th>
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
                  picked={picked}
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
