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

/** One logged serving, with the numbers frozen when it was logged. */
export interface DiaryEntry {
  id: string;
  recipe: string;
  title: string;
  /** null when the recipe no longer exists */
  card_url: string | null;
  /** id of the prep session it came from */
  session: string | null;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  cost: number;
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
}

/** The needed ingredients of one aisle; `aisle` null: not recorded. */
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
