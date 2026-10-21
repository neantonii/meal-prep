/** Typed client for the diary server API. */

export interface CatalogEntry {
  id: string;
  title: string;
  category: string;
  kcal: number;
  protein_g: number;
  cost: number;
}

export interface CatalogGroup {
  category: string;
  recipes: CatalogEntry[];
}

export interface DiaryMeal {
  mealtime: string;
  recipes: string[];
}

export interface DiaryDay {
  date: string;
  meals: DiaryMeal[];
}

export interface DiaryWeek {
  week: string;
  exists: boolean;
  days: DiaryDay[];
  totals: Record<string, number>;
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
  catalog: () => request<{ groups: CatalogGroup[] }>("/api/catalog"),
  diary: (week: string) => request<DiaryWeek>(`/api/diary/${week}`),
  saveDiary: (week: string, payload: { week: string; days: object }) =>
    request<DiaryWeek>(`/api/diary/${week}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteDiary: (week: string) =>
    request<null>(`/api/diary/${week}`, { method: "DELETE" }),
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
