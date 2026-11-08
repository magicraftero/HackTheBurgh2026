import type { Combined, FarmerActions } from './schemas';

// What the page says about our final harvest forecast, worked out from combined.json.

export type FinalScore = { accuracyPct: number; lessErrorPct: number };

/**
 * Scores on the held-back months. Accuracy is 100% minus the typical error in
 * log points (0.20 is "about 20% off"), the same shorthand as analysis/RESULTS.md.
 */
export function finalScore(c: Combined, outcome: keyof Combined['scores']['holdout']): FinalScore | null {
  const row = c.scores.holdout[outcome];
  if (row == null || row.combined == null || !row.b1) return null;
  return { accuracyPct: 100 * (1 - row.combined), lessErrorPct: 100 * (1 - row.combined / row.b1) };
}

export type FinalArea = { area: number; predKg: number; actualKg: number; errorPct: number };

export type FinalLatest = {
  month: string;
  madeOn: string;
  areasLabel: string;
  predKg: number;
  actualKg: number;
  errorPct: number;
  areas: FinalArea[];
};

const errorPct = (pred: number, actual: number) => (pred / actual - 1) * 100;

/** Forecasts are made on the 10th of the month after the one they cover. */
function tenthOfNextMonth(month: string): string {
  const [year, m] = month.split('-').map(Number) as [number, number];
  return m === 12 ? `${year + 1}-01-10` : `${year}-${String(m + 1).padStart(2, '0')}-10`;
}

export function describeAreas(areas: number[]): string {
  const first = areas[0]!;
  const last = areas[areas.length - 1]!;
  return last - first + 1 === areas.length ? `areas ${first}–${last}` : `${areas.length} areas`;
}

/** The newest month with a published figure, added up over the areas forecast. */
export function finalLatest(c: Combined): FinalLatest | null {
  const scored = c.backtest.flatMap((r) =>
    r.window === 'holdout' && r.pred.kg != null && r.actual.kg != null
      ? [{ area: r.area, month: r.month, predKg: r.pred.kg, actualKg: r.actual.kg }]
      : [],
  );
  if (!scored.length) return null;

  const month = scored.reduce((newest, r) => (r.month > newest ? r.month : newest), scored[0]!.month);
  const rows = scored.filter((r) => r.month === month).sort((a, b) => a.area - b.area);
  const predKg = rows.reduce((sum, r) => sum + r.predKg, 0);
  const actualKg = rows.reduce((sum, r) => sum + r.actualKg, 0);
  return {
    month,
    madeOn: tenthOfNextMonth(month),
    areasLabel: describeAreas(rows.map((r) => r.area)),
    predKg,
    actualKg,
    errorPct: errorPct(predKg, actualKg),
    areas: rows.map((r) => ({ ...r, errorPct: errorPct(r.predKg, r.actualKg) })),
  };
}

export type FinalHeadlines = {
  forecasts: number;
  areasLabel: string;
  /** How close each month's total over the areas came, as an accuracy. */
  totalAccuracyPct: number;
};

const average = (xs: number[]) => xs.reduce((sum, x) => sum + x, 0) / xs.length;

/** The held-back forecasts, for the front page. */
export function finalHeadlines(c: Combined): FinalHeadlines | null {
  const rows = c.backtest.flatMap((r) =>
    r.window === 'holdout' && r.pred.kg != null && r.actual.kg != null && r.actual.kg > 0
      ? [{ area: r.area, month: r.month, pred: r.pred.kg, actual: r.actual.kg }]
      : [],
  );
  if (!rows.length) return null;

  const totals = new Map<string, { pred: number; actual: number }>();
  for (const r of rows) {
    const total = totals.get(r.month) ?? { pred: 0, actual: 0 };
    total.pred += r.pred;
    total.actual += r.actual;
    totals.set(r.month, total);
  }
  return {
    forecasts: rows.length,
    areasLabel: describeAreas([...new Set(rows.map((r) => r.area))].sort((a, b) => a - b)),
    totalAccuracyPct: 100 * (1 - average([...totals.values()].map((t) => Math.abs(Math.log(t.pred / t.actual))))),
  };
}

/** A forecast total against the published total for the same month a year earlier, over the same areas. */
export function vsSameMonthLastYear(c: Combined, month: string, areas: number[], kg: number | null): number | null {
  if (kg === null) return null;
  const [year, m] = month.split('-');
  const lastYear = `${Number(year) - 1}-${m}`;
  const rows = c.backtest.filter((r) => r.month === lastYear && areas.includes(r.area) && r.actual.kg != null);
  if (rows.length !== areas.length) return null;
  const total = rows.reduce((sum, r) => sum + r.actual.kg!, 0);
  return total > 0 ? (kg / total - 1) * 100 : null;
}

/** How many fish a national forecast means, and their average size. Null unless every area has a count. */
export function forecastFish(f: FarmerActions): { count: number; avgKg: number } | null {
  const rows = f.areas.filter((a) => f.national.areas.includes(a.area));
  if (!rows.length || rows.length !== f.national.areas.length) return null;
  let count = 0;
  let kg = 0;
  for (const a of rows) {
    if (a.forecast?.count == null || a.forecast.kg == null) return null;
    count += a.forecast.count;
    kg += a.forecast.kg;
  }
  return count > 0 ? { count, avgKg: kg / count } : null;
}
