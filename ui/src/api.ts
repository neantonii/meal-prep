/** Typed client for the diary server API. */

export interface CatalogEntry {
  id: string;
  title: string;
  category: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  cost: number;
}

export interface CatalogGroup {
  category: string;
  recipes: CatalogEntry[];
}

/** One logged serving, with the numbers frozen when it was logged.
 * `recipe` is null for a free-form entry (takeout, eating out), whose
 * unknown numbers are null. */
export interface DiaryEntry {
  id: string;
  recipe: string | null;
  title: string;
  /** null when the recipe no longer exists */
  card_url: string | null;
  /** id of the prep session it came from */
  session: string | null;
  kcal: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  cost: number | null;
  /** free-form: the numbers are a guess */
  estimated: boolean;
  /** what a guess assumed */
  assumptions: string[];
  /** how a guess was made, and the AI's calories range for the whole order */
  estimate_source: "manual" | "ai" | null;
  kcal_low: number | null;
  kcal_high: number | null;
}

/** The numbers a free-form entry is typed with (one portion). */
export const FREE_NUMBERS = ["kcal", "protein_g", "carbs_g", "fat_g", "cost"] as const;
export type FreeNumber = (typeof FREE_NUMBERS)[number];
/** The ones it must have: what totals are made of (cost may be unknown). */
export const REQUIRED_NUMBERS: readonly FreeNumber[] = ["kcal", "protein_g", "carbs_g", "fat_g"];

/** A free-form entry as typed, for one portion: calories and macros, cost
 * if known, and whether the numbers are a guess. */
export interface FreeForm {
  title: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  cost: number | null;
  estimated: boolean;
  /** how a guess was made: typed in, or by AI (with its range and assumptions) */
  source?: "manual" | "ai";
  kcal_low?: number | null;
  kcal_high?: number | null;
  assumptions?: string[];
}

/** One item of an AI estimate. */
export interface EstimatedItem {
  name: string;
  brand: string;
  /** what unsaid detail changes the numbers, as a question ("" when none) */
  question: string;
  quantity: string;
  kcal: number;
  kcal_low: number;
  kcal_high: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  source: "published" | "typical" | "guess";
  assumptions: string[];
}

/** A free-form meal eaten before: its latest numbers. */
export interface Usual extends FreeForm {
  fiber_g: number | null;
  /** ISO date it was last eaten */
  last: string;
  times: number;
}

export interface DiaryMeal {
  mealtime: string;
  entries: DiaryEntry[];
}

/** Plan: after today (auto-fill on). Log: today and earlier. */
export type Mode = "plan" | "log";

export interface DiaryDay {
  date: string;
  mode: Mode;
  /** mealtimes whose prep cycle locked: editable in Admin only */
  settled: Mealtime[];
  meals: DiaryMeal[];
  totals: Record<string, number>;
  /** totals that leave out a meal's unknown number ("kcal", ...) */
  unknown: string[];
  /** totals include a guess */
  estimated: boolean;
}

/** A diary meal: its day and mealtime. */
export interface MealRef {
  date: string;
  mealtime: string;
}

/** One recipe of a prep session: frozen numbers plus made vs eaten. */
export interface SessionItem {
  recipe: string;
  title: string;
  card_url: string | null;
  /** the recipe's category; null once the recipe no longer exists */
  category: string | null;
  batches: number;
  servings: number;
  /** made: batches x servings */
  portions: number;
  /** linked entries, in every week */
  eaten: number;
  /** those entries: which days and mealtimes */
  meals: MealRef[];
  kcal: number;
  protein_g: number;
  cost: number;
}

/** A session card; `id` is null for an empty default placeholder. */
export interface Session {
  id: string | null;
  date: string;
  mode: Mode;
  /** false: an older session linked from this week */
  in_window: boolean;
  items: SessionItem[];
}

/** One session for its own page: the card plus totals. */
/** One ingredient to have on hand by a session, summed over its batches.
 * The package fields are null for lines saved before packages were. */
export interface NeededIngredient {
  ingredient: string;
  name: string;
  card_url: string | null;
  product: string | null;
  package_amount: number | null;
  package_unit: string | null;
  /** how many packages (a fraction is fine) */
  packages: number | null;
  grams: number;
  cost: number;
  /** titles of the recipes that use it */
  recipes: string[];
  /** each recipe's part, and whether it is ticked */
  shares: NeedShare[];
  /** every share ticked for this session */
  have: boolean;
  /** a staple: on hand in every session */
  always: boolean;
}

/** The needed ingredients of one aisle; `aisle` null: not recorded. */
export interface NeedShare {
  recipe: string;
  title: string;
  packages: number | null;
  grams: number;
  cost: number;
  have: boolean;
}

/** A recipe share of an ingredient: what the checklist ticks. */
export interface ShareRef {
  recipe: string;
  ingredient: string;
}

/** On hand: every share ticked for this session, or a staple. */
export function onHand(it: NeededIngredient): boolean {
  return it.have || it.always;
}

/** The shares of a line still to buy (none for a staple). */
export function missingShares(it: NeededIngredient): NeedShare[] {
  return it.always ? [] : it.shares.filter((s) => !s.have);
}

export interface AisleNeeds {
  aisle: string | null;
  cost: number;
  ingredients: NeededIngredient[];
}

export interface SessionDetail {
  session: Session;
  today: string;
  /** ISO week of the session's date (for the way back) */
  week: string;
  totals: Record<string, number>;
  /** what to have on hand by the session, by aisle in walking order */
  needs: AisleNeeds[];
}

export interface DiaryWeek {
  week: string;
  today: string;
  exists: boolean;
  days: DiaryDay[];
  sessions: Session[];
  totals: Record<string, number>;
  unknown: string[];
  estimated: boolean;
}

/** How a new entry links to a session: an id, none, or auto (palette drop). */
export type Link = string | null | "auto";

/** Where an entry goes: a slot and, optionally, its index in that slot. */
export interface Placement {
  date: string;
  mealtime: string;
  position?: number;
}

export const MEALTIMES = ["breakfast", "lunch", "dinner", "snacks"] as const;
export type Mealtime = (typeof MEALTIMES)[number];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (res.status === 204) return null as T;
  const body = (await res.json().catch(() => ({}))) as { detail?: string } & T;
  if (!res.ok) throw new Error(body.detail ?? `HTTP ${res.status}`);
  return body;
}

function send<T>(method: string, path: string, admin: boolean, body?: unknown) {
  const sep = path.includes("?") ? "&" : "?";
  return request<T>(admin ? `${path}${sep}admin=true` : path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const api = {
  currentWeek: () => request<{ week: string }>("/api/week/current"),
  version: () => request<{ version: string; commit: string }>("/api/version"),
  catalog: () => request<{ groups: CatalogGroup[] }>("/api/catalog"),
  diary: (week: string) => request<DiaryWeek>(`/api/diary/${week}`),
  session: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),
  addEntry: (week: string, recipe: string, where: Placement, session: Link, admin: boolean) =>
    send<DiaryWeek>("POST", `/api/diary/${week}/entries`, admin, { ...where, recipe, session }),
  /** Add free-form items (a whole takeout order) to one slot. */
  addOthers: (week: string, where: Placement, items: FreeForm[], admin: boolean) =>
    send<DiaryWeek>("POST", `/api/diary/${week}/others`, admin, { ...where, items }),
  editOther: (week: string, id: string, fields: FreeForm, admin: boolean) =>
    send<DiaryWeek>("PUT", `/api/diary/${week}/others/${id}`, admin, fields),
  usuals: () => request<Usual[]>("/api/usuals"),
  /** Whether AI estimates are on (the host has an API key). */
  estimateStatus: () => request<{ available: boolean; model: string | null }>("/api/estimate"),
  /** Split a messy description into items with estimated numbers. */
  estimate: (text: string) =>
    send<{ items: EstimatedItem[] }>("POST", "/api/estimate", false, { text }),
  removeEntry: (week: string, id: string, admin: boolean) =>
    send<DiaryWeek>("DELETE", `/api/diary/${week}/entries/${id}`, admin),
  moveEntry: (week: string, id: string, where: Placement, admin: boolean) =>
    send<DiaryWeek>("PATCH", `/api/diary/${week}/entries/${id}`, admin, where),
  linkEntry: (week: string, id: string, session: string | null, admin: boolean) =>
    send<DiaryWeek>("PUT", `/api/diary/${week}/entries/${id}/session`, admin, { session }),
  /** Link to the session on `date`, created when that day has none yet. */
  linkEntryToDay: (week: string, id: string, date: string, admin: boolean) =>
    send<DiaryWeek>("PUT", `/api/diary/${week}/entries/${id}/session`, admin, {
      session_date: date,
    }),
  removeItem: (week: string, session: string, recipe: string, admin: boolean) =>
    send<DiaryWeek>("DELETE", `/api/sessions/${session}/items/${recipe}?week=${week}`, admin),
  deleteSession: (week: string, session: string, admin: boolean) =>
    send<DiaryWeek>("DELETE", `/api/sessions/${session}?week=${week}`, admin),
  /** Tick (or untick) recipe shares on the session's shopping checklist. */
  setHave: (session: string, shares: ShareRef[], have: boolean) =>
    send<SessionDetail>("PUT", `/api/sessions/${session}/have`, false, { shares, have }),
  /** Mark an ingredient as always on hand, in every session (or not). */
  setAlways: (session: string, ingredient: string, always: boolean) =>
    send<SessionDetail>("PUT", `/api/sessions/${session}/always/${ingredient}`, false, {
      always,
    }),
};

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Short day label for an ISO date ("2026-11-01" -> "Sun 1 Nov"). */
export function dayLabel(date: string): string {
  const d = new Date(`${date}T00:00:00Z`);
  return `${WEEKDAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** Color class for a session on `date`, by its slot on the week page that
 * starts on `monday`: the four standard slots always get the same colors
 * (Sunday before c0, Tuesday c1, Thursday c2, the week's Sunday c3), any
 * other day of the page c4, an older session c5. */
export function sessionColor(date: string, monday: string): string {
  const offset = Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${monday}T00:00:00Z`)) / 86400000);
  const slots: Record<number, string> = { [-1]: "c0", 1: "c1", 3: "c2", 6: "c3" };
  return slots[offset] ?? (offset >= -1 && offset <= 6 ? "c4" : "c5");
}

/** "Mon lunch · Wed dinner" for a list of meals. */
export function mealsLabel(meals: MealRef[]): string {
  return meals.map((m) => `${dayLabel(m.date).split(" ")[0]} ${m.mealtime}`).join(" · ");
}

/** Shift an ISO week id ("2026-W43") by `delta` weeks. */
export function shiftWeek(week: string, delta: number): string {
  const [y, n] = week.split("-W").map(Number);
  const monday = new Date(Date.UTC(y, 0, 4 + (n - 1) * 7));
  const dow = (monday.getUTCDay() + 6) % 7;
  monday.setUTCDate(monday.getUTCDate() - dow + delta * 7);
  const thursday = new Date(monday);
  thursday.setUTCDate(thursday.getUTCDate() + 3);
  const isoYear = thursday.getUTCFullYear();
  const jan4 = new Date(Date.UTC(isoYear, 0, 4));
  const jan4dow = (jan4.getUTCDay() + 6) % 7;
  const w1monday = new Date(jan4);
  w1monday.setUTCDate(w1monday.getUTCDate() - jan4dow);
  const num = Math.round((monday.getTime() - w1monday.getTime()) / 604800000) + 1;
  return `${isoYear}-W${String(num).padStart(2, "0")}`;
}

/** "≈ 1,008" for a guess, "? " when unknown: how a number reads. */
export function approx(value: number | null, estimated: boolean, unit = ""): string {
  if (value === null) return `?${unit}`;
  return `${estimated ? "≈ " : ""}${Math.round(value).toLocaleString("en-US")}${unit}`;
}

/** The prefix of a total: "≥ " when it leaves out an unknown number,
 * "≈ " when it includes a guess. */
export function totalMark(unknown: string[], estimated: boolean, name: string): string {
  if (unknown.includes(name)) return "≥ ";
  return estimated ? "≈ " : "";
}
