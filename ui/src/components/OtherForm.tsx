import { useEffect, useMemo, useRef, useState } from "react";
import { FREE_NUMBERS, api, approx, dayLabel, type FreeForm, type FreeNumber, type Usual } from "../api";

interface Props {
  /** Where it goes, for the heading ("Fri 6 Nov lunch"). */
  date: string;
  meal: string;
  /** Editing an entry: its current fields; adding: null. */
  initial: FreeForm | null;
  onSave: (fields: FreeForm) => void;
  onClose: () => void;
}

const LABELS: Record<FreeNumber, string> = {
  kcal: "kcal",
  protein_g: "protein g",
  carbs_g: "carbs g",
  fat_g: "fat g",
  cost: "cost $",
};
const PORTIONS: [number, string][] = [
  [0.25, "¼"],
  [0.5, "½"],
  [0.75, "¾"],
  [1, "1"],
  [1.5, "1½"],
  [2, "2"],
];
const EMPTY: FreeForm = {
  title: "",
  kcal: null,
  protein_g: null,
  carbs_g: null,
  fat_g: null,
  cost: null,
  portion: 1,
  estimated: true,
};

type Draft = Omit<FreeForm, FreeNumber> & Record<FreeNumber, string>;

const toDraft = (f: FreeForm): Draft => ({
  ...f,
  ...(Object.fromEntries(
    FREE_NUMBERS.map((n) => [n, f[n] === null ? "" : String(Math.round(f[n] * 100) / 100)]),
  ) as Record<FreeNumber, string>),
});

/** A takeout or eating-out meal: a title and the whole order's numbers
 * (blank = unknown), the share eaten and whether the numbers are a guess.
 * Typing a title offers meals eaten before; picking one copies its numbers. */
export default function OtherForm({ date, meal, initial, onSave, onClose }: Props) {
  const [draft, setDraft] = useState<Draft>(toDraft(initial ?? EMPTY));
  const [usuals, setUsuals] = useState<Usual[]>([]);
  const [suggest, setSuggest] = useState(initial === null);
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    titleRef.current?.focus();
    api.usuals().then(setUsuals).catch(() => setUsuals([]));
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const matches = useMemo(() => {
    const q = draft.title.trim().toLowerCase();
    return usuals.filter((u) => u.title.toLowerCase().includes(q)).slice(0, 8);
  }, [usuals, draft.title]);

  const number = (n: FreeNumber): number | null => {
    const v = draft[n].trim();
    return v === "" || Number.isNaN(Number(v)) ? null : Number(v);
  };
  const fields = (): FreeForm => ({
    ...draft,
    title: draft.title.trim(),
    ...(Object.fromEntries(FREE_NUMBERS.map((n) => [n, number(n)])) as Record<FreeNumber, number | null>),
  });
  const pick = (u: Usual) => {
    setDraft(toDraft({ ...u, portion: draft.portion }));
    setSuggest(false);
  };
  const invalid = FREE_NUMBERS.some((n) => draft[n].trim() !== "" && (number(n) === null || number(n)! < 0));
  const canSave = draft.title.trim() !== "" && !invalid;
  const kcal = number("kcal");

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form
        className="modal other-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSave) onSave(fields());
        }}
      >
        <h2>
          {initial ? "Edit" : "Add"} takeout · {dayLabel(date)} {meal}
        </h2>
        <label className="field">
          <span>What</span>
          <input
            ref={titleRef}
            value={draft.title}
            placeholder="McChicken meal, small fries, 6 nuggets"
            maxLength={200}
            onChange={(e) => {
              setDraft({ ...draft, title: e.target.value });
              setSuggest(true);
            }}
          />
        </label>
        {suggest && matches.length > 0 && (
          <ul className="usuals" aria-label="Eaten before">
            {matches.map((u) => (
              <li key={u.title}>
                <button type="button" onClick={() => pick(u)}>
                  <span className="usual-title">{u.title}</span>
                  <span className="usual-meta">
                    {approx(u.kcal, u.estimated, " kcal")} · {approx(u.protein_g, false, " P")}
                    {u.cost !== null && ` · $${u.cost.toFixed(2)}`} · {dayLabel(u.last)}
                    {u.times > 1 && ` · ${u.times}×`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <fieldset className="numbers">
          <legend>The whole order (blank = unknown)</legend>
          {FREE_NUMBERS.map((n) => (
            <label key={n} className="field">
              <span>{LABELS[n]}</span>
              <input
                inputMode="decimal"
                value={draft[n]}
                aria-invalid={draft[n].trim() !== "" && (number(n) === null || number(n)! < 0)}
                onChange={(e) => setDraft({ ...draft, [n]: e.target.value })}
              />
            </label>
          ))}
        </fieldset>
        <div className="row">
          <span>Ate</span>
          <div className="portions" role="radiogroup" aria-label="Share of the order eaten">
            {PORTIONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={draft.portion === value}
                className={draft.portion === value ? "on" : ""}
                onClick={() => setDraft({ ...draft, portion: value })}
              >
                {label}
              </button>
            ))}
          </div>
          {draft.portion !== 1 && kcal !== null && (
            <span className="hint">= {Math.round(kcal * draft.portion)} kcal</span>
          )}
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={draft.estimated}
            onChange={(e) => setDraft({ ...draft, estimated: e.target.checked })}
          />
          A guess (shown with ≈); untick for numbers from the menu or label
        </label>
        <div className="actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!canSave}>
            {initial ? "Save" : "Add"}
          </button>
        </div>
      </form>
    </div>
  );
}
