import type { Combined } from './schemas';

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

function describeAreas(areas: number[]): string {
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
