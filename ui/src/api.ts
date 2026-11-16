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
  /** display name, the same as the recipe cards' badge */
  label: string;
  /** what belongs in the category, for a hover hint */
  description: string;
  recipes: CatalogEntry[];
}

/** What every logged serving shows: calories and macros, as logged. */
interface EntryBase {
  id: string;
  title: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

/** A serving of a catalog recipe, with the numbers frozen when logged. */
export interface RecipeEntry extends EntryBase {
  kind: "recipe";
  recipe: string;
  /** null when the recipe no longer exists */
  card_url: string | null;
  /** id of the prep session it came from */
  session: string | null;
  /** eaten later than the dish keeps in the fridge: frozen in between */
  frozen: boolean;
  /** whether the dish freezes well; null when not recorded */
  freezer_friendly: boolean | null;
  fiber_g: number;
  cost: number;
}

/** A takeout meal: never from a session; its cost only if known. */
export interface TakeoutEntry extends EntryBase {
  kind: "takeout";
  cost: number | null;
}

/** One logged serving, told apart by `kind`. */
export type DiaryEntry = RecipeEntry | TakeoutEntry;

/** A takeout meal as typed (one portion): calories and macros, cost if known. */
export interface TakeoutFields {
  title: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  cost: number | null;
}

/** One item of an AI estimate (shown while reviewing, never stored). */
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
  /** rough typical price in CAD */
  price: number;
  source: "published" | "typical" | "guess";
  assumptions: string[];
}

/** A takeout meal eaten before: its latest numbers. */
export interface Usual extends TakeoutFields {
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
  /** the category's display name; null once the recipe no longer exists */
  category_label: string | null;
  batches: number;
  servings: number;
  /** made: batches x servings */
  portions: number;
  /** its meals on days, in every week */
  eaten: number;
  /** those meals: which days and mealtimes */
  meals: MealRef[];
  /** its meals with no day yet */
  unassigned: number;
  /** its meals thrown away */
  binned: number;
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

/** The unassigned portions of one recipe, over every session. */
export interface UnassignedRecipe {
  recipe: string;
  title: string;
  card_url: string | null;
  count: number;
  kcal: number;
  protein_g: number;
  /** whether the dish freezes well; null when not recorded */
  freezer_friendly: boolean | null;
  /** where they were (or will be) cooked, latest session first */
  sources: { session: string; date: string; count: number }[];
  /** the portions' ids, oldest session first */
  meals: string[];
}

/** A portion thrown away. */
export interface BinnedMeal {
  id: string;
  recipe: string;
  title: string;
  cost: number;
  /** the day it went to the bin */
  binned: string;
  session: string;
  /** null when the session is gone */
  session_date: string | null;
}

/** Everything thrown away so far; `meals` latest first. */
export interface Bin {
  count: number;
  cost: number;
  meals: BinnedMeal[];
}

export interface DiaryWeek {
  week: string;
  today: string;
  exists: boolean;
  days: DiaryDay[];
  sessions: Session[];
  /** portions with no day yet, by recipe */
  unassigned: UnassignedRecipe[];
  bin: Bin;
  totals: Record<string, number>;
}

/** Portions of a recipe line no meal accounts for: only when something went
 * wrong (an interrupted edit, a hand-edited file, a session from before
 * portions were meals). */
export function spareOf(it: SessionItem): number {
  return it.portions - it.eaten - it.unassigned - it.binned;
}

/** The two homes without a date. */
export type SlotName = "unassigned" | "bin";

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
  /** Cook one more batch of `recipe` with one portion on this day; in
   * `session`, or (null) the session of the meal's prep cycle. */
  addEntry: (week: string, recipe: string, where: Placement, session: string | null, admin: boolean) =>
    send<DiaryWeek>("POST", `/api/diary/${week}/entries`, admin, { ...where, recipe, session }),
  /** Put an unassigned portion of `recipe` on a day. */
  takeUnassigned: (week: string, recipe: string, where: Placement, admin: boolean) =>
    send<DiaryWeek>("POST", `/api/diary/${week}/unassigned`, admin, { ...where, recipe }),
  /** Add takeout items (a whole order) to one slot. */
  addTakeout: (week: string, where: Placement, items: TakeoutFields[], admin: boolean) =>
    send<DiaryWeek>("POST", `/api/diary/${week}/takeout`, admin, { ...where, items }),
  editTakeout: (week: string, id: string, fields: TakeoutFields, admin: boolean) =>
    send<DiaryWeek>("PUT", `/api/diary/${week}/takeout/${id}`, admin, fields),
  usuals: () => request<Usual[]>("/api/usuals"),
  /** Whether AI estimates are on (the host has an API key). */
  estimateStatus: () => request<{ available: boolean; model: string | null }>("/api/estimate"),
  /** Split a messy description into items with estimated numbers. */
  /** `images`: photos as data URLs (meal, menu or receipt), up to 3. */
  estimate: (text: string, images: string[] = []) =>
    send<{ items: EstimatedItem[] }>("POST", "/api/estimate", false, { text, images }),
  removeEntry: (week: string, id: string, admin: boolean) =>
    send<DiaryWeek>("DELETE", `/api/diary/${week}/entries/${id}`, admin),
  moveEntry: (week: string, id: string, where: Placement, admin: boolean) =>
    send<DiaryWeek>("PATCH", `/api/diary/${week}/entries/${id}`, admin, where),
  /** Move a meal (from a day or the other slot) to unassigned or the bin. */
  moveToSlot: (week: string, id: string, slot: SlotName, admin: boolean) =>
    send<DiaryWeek>("PUT", `/api/diary/${week}/entries/${id}/slot`, admin, { slot }),
  /** Remove one batch; its portions are taken from unassigned. */
  removeBatch: (week: string, session: string, recipe: string, admin: boolean) =>
    send<DiaryWeek>("DELETE", `/api/sessions/${session}/items/${recipe}/batch?week=${week}`, admin),
  /** Move a whole recipe line to another session, or to the one on a day
   * (created when that day has none yet). */
  moveItem: (
    week: string,
    session: string,
    recipe: string,
    to: { session: string } | { date: string },
    admin: boolean,
  ) =>
    send<DiaryWeek>("PUT", `/api/sessions/${session}/items/${recipe}/session?week=${week}`, admin, to),
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
