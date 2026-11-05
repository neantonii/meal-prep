import { useEffect, useMemo, useRef, useState } from "react";
import {
  FREE_NUMBERS,
  REQUIRED_NUMBERS,
  api,
  approx,
  dayLabel,
  type EstimatedItem,
  type FreeForm,
  type FreeNumber,
  type Usual,
} from "../api";

interface Props {
  /** Where it goes, for the heading ("Fri 6 Nov lunch"). */
  date: string;
  meal: string;
  /** Editing an entry: its current fields; adding: null. */
  initial: FreeForm | null;
  /** Adding: every item, in order; editing: the one entry. */
  onSave: (items: FreeForm[]) => void;
  onClose: () => void;
}

const LABELS: Record<FreeNumber, string> = {
  kcal: "kcal",
  protein_g: "protein",
  carbs_g: "carbs",
  fat_g: "fat",
  cost: "$",
};

/** One item being edited: numbers as typed (blank = unknown), plus what
 * an AI estimate said about it. */
interface Row {
  key: number;
  title: string;
  nums: Record<FreeNumber, string>;
  estimated: boolean;
  source: "manual" | "ai";
  kcal_low: number | null;
  kcal_high: number | null;
  assumptions: string[];
  /** from the AI: an unsaid detail that changes the numbers */
  question: string;
  /** from the AI: the amount it assumed, and where its numbers come from */
  quantity: string;
  basis: string;
}

let nextKey = 1;
const fmt = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(Math.round(v * 10) / 10));

function rowFrom(f: FreeForm | null): Row {
  return {
    key: nextKey++,
    title: f?.title ?? "",
    nums: Object.fromEntries(FREE_NUMBERS.map((n) => [n, fmt(f?.[n])])) as Record<FreeNumber, string>,
    estimated: f?.estimated ?? true,
    source: f?.source ?? "manual",
    kcal_low: f?.kcal_low ?? null,
    kcal_high: f?.kcal_high ?? null,
    assumptions: f?.assumptions ?? [],
    question: "",
    quantity: "",
    basis: "",
  };
}

const blank = (): Row => rowFrom(null);

function rowFromEstimate(item: EstimatedItem): Row {
  return {
    ...rowFrom({
      title: item.name,
      kcal: item.kcal,
      protein_g: item.protein_g,
      carbs_g: item.carbs_g,
      fat_g: item.fat_g,
      cost: null,
      estimated: true,
      source: "ai",
      kcal_low: item.kcal_low,
      kcal_high: item.kcal_high,
      assumptions: item.assumptions,
    }),
    question: item.question,
    quantity: item.quantity,
    basis: item.source,
  };
}

const parse = (v: string): number | null => {
  const t = v.trim();
  return t === "" || Number.isNaN(Number(t)) ? null : Number(t);
};
const bad = (v: string) => v.trim() !== "" && (parse(v) === null || parse(v)! < 0);
/** A number the row can't save with: malformed, or a required one left blank. */
const wrong = (r: Row, n: FreeNumber) => bad(r.nums[n]) || (REQUIRED_NUMBERS.includes(n) && r.nums[n].trim() === "");

function toFields(r: Row): FreeForm {
  return {
    title: r.title.trim(),
    kcal: parse(r.nums.kcal) ?? 0,
    protein_g: parse(r.nums.protein_g) ?? 0,
    carbs_g: parse(r.nums.carbs_g) ?? 0,
    fat_g: parse(r.nums.fat_g) ?? 0,
    cost: parse(r.nums.cost),
    estimated: r.estimated,
    source: r.source,
    kcal_low: r.kcal_low,
    kcal_high: r.kcal_high,
    assumptions: r.assumptions,
  };
}

/** Takeout or eating out. Adding: describe the meal (messy is fine) and let
 * the AI split and estimate it, pick meals eaten before, or type items in;
 * every row is editable and they are saved together. Editing: one entry. */
export default function OtherForm({ date, meal, initial, onSave, onClose }: Props) {
  const editing = initial !== null;
  const [rows, setRows] = useState<Row[]>(editing ? [rowFrom(initial)] : []);
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [usuals, setUsuals] = useState<Usual[]>([]);
  const [ai, setAi] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const firstRef = useRef<HTMLTextAreaElement & HTMLInputElement>(null);

  useEffect(() => {
    firstRef.current?.focus();
    if (editing) return;
    api.usuals().then(setUsuals).catch(() => setUsuals([]));
    api
      .estimateStatus()
      .then((s) => setAi(s.available))
      .catch(() => setAi(false));
  }, [editing]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (q === "") return [];
    return usuals.filter((u) => u.title.toLowerCase().includes(q)).slice(0, 8);
  }, [usuals, search]);

  const update = (key: number, change: Partial<Row>) =>
    setRows((cur) => cur.map((r) => (r.key === key ? { ...r, ...change } : r)));

  const estimate = async () => {
    if (text.trim() === "" || busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const { items } = await api.estimate(text);
      // A new estimate replaces the previous one; picked and typed rows stay.
      setRows((cur) => [...cur.filter((r) => r.source !== "ai" && r.title.trim() !== ""), ...items.map(rowFromEstimate)]);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const pick = (u: Usual) => {
    setRows((cur) => [...cur.filter((r) => r.title.trim() !== ""), rowFrom(u)]);
    setSearch("");
  };

  const valid = rows.length > 0 && rows.every((r) => r.title.trim() !== "" && !FREE_NUMBERS.some((n) => wrong(r, n)));
  const total = rows.reduce((sum, r) => sum + (parse(r.nums.kcal) ?? 0), 0);
  const guessed = rows.some((r) => r.estimated);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form
        className="modal other-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (valid) onSave(rows.map(toFields));
        }}
      >
        <h2>
          {editing ? "Edit" : "Add"} takeout · {dayLabel(date)} {meal}
        </h2>
        {!editing && ai && (
          <div className="describe">
            <textarea
              ref={firstRef}
              rows={2}
              value={text}
              maxLength={1000}
              placeholder="What did you eat? e.g. mcdonalds meal, mcchicken, small fries, 6 nuggets + sweet and sour"
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  void estimate();
                }
              }}
            />
            <button type="button" className="primary" disabled={busy || text.trim() === ""} onClick={() => void estimate()}>
              {busy ? "Estimating…" : rows.some((r) => r.source === "ai") ? "Estimate again" : "Estimate"}
            </button>
          </div>
        )}
        {problem && <div className="problem">{problem}</div>}
        {!editing && (
          <div className="past">
            <input
              ref={ai ? undefined : firstRef}
              value={search}
              placeholder="Add a meal you had before…"
              onChange={(e) => setSearch(e.target.value)}
            />
            {matches.length > 0 && (
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
          </div>
        )}

        {rows.length > 0 && (
          <ol className="items">
            {rows.map((r, i) => (
              <li key={r.key} className="item">
                <div className="item-head">
                  <input
                    ref={editing && i === 0 ? firstRef : undefined}
                    className="item-title"
                    value={r.title}
                    placeholder="Name, with the brand"
                    maxLength={200}
                    aria-label="Name"
                    onChange={(e) => update(r.key, { title: e.target.value })}
                  />
                  {!editing && (
                    <button
                      type="button"
                      className="x"
                      title="Remove this item"
                      onClick={() => setRows((cur) => cur.filter((x) => x.key !== r.key))}
                    >
                      ×
                    </button>
                  )}
                </div>
                {r.question && <div className="question">{r.question}</div>}
                <div className="numbers">
                  {FREE_NUMBERS.map((n) => (
                    <label key={n}>
                      <input
                        inputMode="decimal"
                        value={r.nums[n]}
                        aria-label={LABELS[n]}
                        aria-invalid={bad(r.nums[n])}
                        aria-required={REQUIRED_NUMBERS.includes(n)}
                        placeholder={REQUIRED_NUMBERS.includes(n) ? " " : "?"}
                        onChange={(e) => update(r.key, { nums: { ...r.nums, [n]: e.target.value } })}
                      />
                      <span>{LABELS[n]}</span>
                    </label>
                  ))}
                </div>
                <div className="item-foot">
                  <label className="check" title="Untick for numbers from the menu or label">
                    <input
                      type="checkbox"
                      checked={r.estimated}
                      onChange={(e) => update(r.key, { estimated: e.target.checked })}
                    />
                    guess
                  </label>
                </div>
                {(r.source === "ai" || r.assumptions.length > 0) && (
                  <div className="ai-note">
                    {r.kcal_low !== null && r.kcal_high !== null && (
                      <span>
                        {Math.round(r.kcal_low)}–{Math.round(r.kcal_high)} kcal
                      </span>
                    )}
                    {r.quantity && <span>{r.quantity}</span>}
                    {r.basis && <span>{r.basis === "published" ? "menu values" : r.basis}</span>}
                    {r.assumptions.length > 0 && <span>assumed: {r.assumptions.join("; ")}</span>}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
        {!editing && (
          <button type="button" className="add-row" onClick={() => setRows((cur) => [...cur, blank()])}>
            + type an item
          </button>
        )}
        <div className="actions">
          {rows.length > 0 && (
            <span className="sum">
              {rows.length} item{rows.length === 1 ? "" : "s"} · {guessed ? "≈ " : ""}
              {Math.round(total).toLocaleString("en-US")} kcal
            </span>
          )}
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!valid}>
            {editing ? "Save" : `Add${rows.length > 1 ? ` ${rows.length}` : ""}`}
          </button>
        </div>
      </form>
    </div>
  );
}
