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

export interface DiaryDay {
  date: string;
  meals: DiaryMeal[];
  totals: Record<string, number>;
}

export interface DiaryWeek {
  week: string;
  exists: boolean;
  days: DiaryDay[];
  totals: Record<string, number>;
}

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

export const api = {
  currentWeek: () => request<{ week: string }>("/api/week/current"),
  version: () => request<{ version: string; commit: string }>("/api/version"),
  catalog: () => request<{ groups: CatalogGroup[] }>("/api/catalog"),
  diary: (week: string) => request<DiaryWeek>(`/api/diary/${week}`),
  addEntry: (week: string, recipe: string, where: Placement) =>
    request<DiaryWeek>(`/api/diary/${week}/entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...where, recipe }),
    }),
  removeEntry: (week: string, id: string) =>
    request<DiaryWeek>(`/api/diary/${week}/entries/${id}`, { method: "DELETE" }),
  moveEntry: (week: string, id: string, where: Placement) =>
    request<DiaryWeek>(`/api/diary/${week}/entries/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(where),
    }),
};

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
