// Builds the mock findings: small, schema-correct copies of every contract
// file, in the before-freeze ("pre") and after-freeze ("post") shapes of
// docs/plans/00-shared.md. Every number here is made up. Deterministic, so
// regenerating gives the same files.

import type {
  AreaMonth,
  Channels,
  ChartSpec,
  Combined,
  Drivers,
  FarmerActions,
  Farms,
  FarmWeeksIndex,
  FarmWeeksYear,
  Nowcast,
  Price,
  Trap,
} from '../src/data/schemas';

export type MockScenario = 'pre' | 'post';

// ---- Helpers ----

function seeded(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
type Rand = () => number;
const jitter = (rand: Rand, size: number) => (rand() - 0.5) * 2 * size;

// The contract's rounding: lice and temperature to 2 decimals, other measured values to 4 s.f.
const r2 = (x: number) => Math.round(x * 100) / 100;
const sig4 = (x: number) => (x === 0 ? 0 : Number(x.toPrecision(4)));

const DAY = 86_400_000;
const pad = (n: number) => String(n).padStart(2, '0');

function isoWeekOf(t: number): string {
  const dow = new Date(t).getUTCDay() || 7;
  const thursday = t + (4 - dow) * DAY;
  const year = new Date(thursday).getUTCFullYear();
  const week = Math.floor((thursday - Date.UTC(year, 0, 1)) / DAY / 7) + 1;
  return `${year}-W${pad(week)}`;
}

export function mondayOf(isoWeek: string): number {
  const year = Number(isoWeek.slice(0, 4));
  const week = Number(isoWeek.slice(6));
  const jan4 = Date.UTC(year, 0, 4);
  const jan4dow = new Date(jan4).getUTCDay() || 7;
  return jan4 - (jan4dow - 1) * DAY + (week - 1) * 7 * DAY;
}

function weeksBetween(from: string, to: string): string[] {
  const out: string[] = [];
  for (let t = mondayOf(from); t <= mondayOf(to); t += 7 * DAY) out.push(isoWeekOf(t));
  return out;
}

function monthsBetween(from: string, to: string): string[] {
  const out: string[] = [];
  let y = Number(from.slice(0, 4));
  let m = Number(from.slice(5));
  const end = Number(to.slice(0, 4)) * 12 + Number(to.slice(5));
  while (y * 12 + m <= end) {
    out.push(`${y}-${pad(m)}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

const isoDate = (t: number) => new Date(t).toISOString().slice(0, 10);
const weekNo = (w: string) => Number(w.slice(6));
const monthNo = (m: string) => Number(m.slice(5));
const season = (phase: number, period: number, offset: number) =>
  Math.sin(((phase - offset) / period) * 2 * Math.PI);

function tenthOfNextMonth(month: string): string {
  let y = Number(month.slice(0, 4));
  let m = Number(month.slice(5)) + 1;
  if (m > 12) {
    m = 1;
    y += 1;
  }
  return `${y}-${pad(m)}-10`;
}

const last = <T>(xs: readonly T[]): T => xs[xs.length - 1]!;

// ---- Finding 1: farms and farm weeks ----

// Rough latitude and longitude for each production area, south to north.
const AREA_LAT = [0, 58.9, 59.6, 60.3, 61.4, 62.3, 63.4, 64.8, 66.6, 68.2, 68.9, 69.6, 70.2, 70.7];
const AREA_LON = [0, 6.0, 5.6, 5.2, 5.0, 6.0, 8.6, 11.2, 13.0, 15.0, 17.0, 19.5, 22.5, 25.5];
const FARM_COUNT = 40;

function makeFarms(rand: Rand): Farms {
  return Array.from({ length: FARM_COUNT }, (_, i) => {
    const area = 1 + (i % 13);
    return {
      id: 10001 + i,
      name: `Mock site ${i + 1}`,
      lat: sig4(AREA_LAT[area]! + jitter(rand, 0.3)),
      lon: sig4(AREA_LON[area]! + jitter(rand, 0.4)),
      area,
      capacity_t: i % 9 === 4 ? null : sig4(1000 + rand() * 5000),
    };
  });
}

function makeFarmYear(year: number, weeks: string[], farms: Farms, withDisease: boolean, rand: Rand): FarmWeeksYear {
  // A few farms are fallow in odd years, so ids differ between years.
  const ids = farms.filter((_, j) => j % 10 !== 9 || year % 2 === 0).map((f) => f.id);
  const mobile: (number | null)[][] = [];
  const treated: (0 | 1 | null)[][] = [];
  const disease: (0 | 1 | null)[][] = [];
  const temp: (number | null)[][] = [];
  for (const week of weeks) {
    const lice = season(weekNo(week), 52, 10);
    const warm = season(weekNo(week), 52, 18);
    const rows = { m: [] as (number | null)[], t: [] as (0 | 1 | null)[], d: [] as (0 | 1 | null)[], c: [] as (number | null)[] };
    for (let j = 0; j < ids.length; j++) {
      if (rand() < 0.08) {
        rows.m.push(null);
        rows.t.push(null);
        rows.d.push(null);
        rows.c.push(null);
        continue;
      }
      const m = Math.max(0, 0.35 + 0.3 * lice + jitter(rand, 0.2));
      rows.m.push(r2(m));
      rows.t.push(rand() < 0.04 + 0.15 * Math.max(0, m - 0.5) ? 1 : 0);
      rows.d.push(rand() < 0.02 ? 1 : 0);
      rows.c.push(r2(9 + 5 * warm + jitter(rand, 0.6)));
    }
    mobile.push(rows.m);
    treated.push(rows.t);
    disease.push(rows.d);
    temp.push(rows.c);
  }
  return { year, weeks, ids, mobile, treated, temp, ...(withDisease ? { disease } : {}) };
}

// ---- Harvest by area and month ----

const AREA_BASE_KG = [0, 9e6, 14e6, 22e6, 18e6, 12e6, 20e6, 15e6, 11e6, 13e6, 16e6, 10e6, 8e6, 6e6];

function makeAreaMonth(rand: Rand): AreaMonth {
  const rows: AreaMonth = [];
  for (const month of monthsBetween('2025-10', '2026-09')) {
    for (let area = 1; area <= 13; area++) {
      const kg = AREA_BASE_KG[area]! * (1 + 0.25 * season(monthNo(month), 12, 5) + jitter(rand, 0.1));
      const avg = 4.9 + jitter(rand, 0.4);
      rows.push({
        area,
        month,
        kg: sig4(kg),
        count: Math.round(kg / avg),
        avg_kg: sig4(avg),
        volume_anom: sig4(jitter(rand, 0.1)),
        count_anom: sig4(jitter(rand, 0.12)),
        weight_anom: sig4(jitter(rand, 0.05)),
        mobile_idx: r2(0.3 + rand() * 0.5),
        dd_anom: sig4(jitter(rand, 20)),
        feed_rate_anom: sig4(jitter(rand, 0.05)),
        mortality_anom: area === 13 ? null : sig4(jitter(rand, 0.2)),
      });
    }
  }
  return rows;
}

// ---- Finding 2: the trap ----

function makeTrap(rand: Rand): Trap {
  const weeks = weeksBetween('2024-W01', '2026-W44');
  const series = weeks.map((week) => {
    const s = season(weekNo(week), 52, 10);
    const driverAnom = jitter(rand, 0.1);
    const priceAnom = jitter(rand, 0.04);
    return {
      week,
      driver: r2(0.4 + 0.3 * s + driverAnom),
      price: sig4(4.4 - 0.15 * s + priceAnom),
      driver_anom: sig4(driverAnom),
      price_anom: sig4(priceAnom),
    };
  });
  return {
    from: weeks[0]!,
    to: last(weeks),
    highlight: 'mobile_idx',
    drivers: [
      { driver: 'mobile_idx', label: 'Mobile lice per fish', raw_r: -0.61, anom_r: -0.08 },
      { driver: 'treat_rate', label: 'Treatment rate', raw_r: -0.42, anom_r: 0.04 },
      { driver: 'temp_c', label: 'Sea temperature', raw_r: -0.7, anom_r: 0.05 },
      { driver: 'disease_share', label: 'Sites with ISA or PD', raw_r: 0.12, anom_r: null },
    ],
    series,
  };
}

// ---- Findings 3 and 6: channels ----

function makeChannels(scenario: MockScenario, rand: Rand): Channels {
  const windows: [string, string][] = [
    ['lice', '0-3'],
    ['temp', '1-3'],
    ['feed', '0-2'],
    ['mortality', '0-3'],
  ];
  const bins = windows.flatMap(([driver, window]) =>
    [1, 2, 3].map((tercile) => ({
      driver,
      tercile,
      window,
      count_anom: sig4((tercile - 2) * 0.03 + jitter(rand, 0.01)),
      weight_anom: sig4(-(tercile - 2) * 0.02 + jitter(rand, 0.005)),
      n: 300 + Math.floor(rand() * 40),
    })),
  );
  if (scenario === 'pre') return { bins }; // no panel before the freeze
  return {
    bins,
    panel: [
      { test: 'M1', outcome: 'log_count', driver: 'mobile_lice', lags: '0-3', coef_sum: 0.031, lo: 0.012, hi: 0.05, pass: true },
      { test: 'M1', outcome: 'log_avg_kg', driver: 'mobile_lice', lags: '0-3', coef_sum: -0.008, lo: -0.021, hi: 0.005, pass: false },
      { test: 'M1', outcome: 'log_count', driver: 'treat_rate', lags: '0-3', coef_sum: -0.012, lo: -0.03, hi: 0.006, pass: null },
      { test: 'M2', outcome: 'log_avg_kg', driver: 'dd_below14', lags: '1-3', coef_sum: 0.0021, lo: 0.0008, hi: 0.0034, pass: true },
    ],
  };
}

// ---- Finding 4: the nowcast ----

type KCW = { kg: number | null; count: number | null; avg_kg: number | null };

function makeNowcast(scenario: MockScenario, rand: Rand): Nowcast {
  const models = ['b0', 'b1', 'drivers'];
  const noise: Record<string, number> = { b0: 0.2, b1: 0.15, drivers: 0.12 };
  const windows = { dev: ['2021-01', '2024-12'] as [string, string], holdout: ['2025-01', '2026-09'] as [string, string] };
  const months: [string, 'dev' | 'holdout'][] = [
    ...monthsBetween('2024-01', '2024-12').map((m) => [m, 'dev'] as [string, 'dev']),
    ...(scenario === 'post' ? monthsBetween(...windows.holdout).map((m) => [m, 'holdout'] as [string, 'holdout']) : []),
  ];

  const backtest: Nowcast['backtest'] = [];
  for (const [month, window] of months) {
    for (let area = 1; area <= 13; area++) {
      const kg = AREA_BASE_KG[area]! * (1 + 0.25 * season(monthNo(month), 12, 5) + jitter(rand, 0.1));
      const avg = 4.9 + jitter(rand, 0.4);
      const actual: KCW = { kg: sig4(kg), count: Math.round(kg / avg), avg_kg: sig4(avg) };
      const pred: Record<string, KCW> = {};
      for (const m of models) {
        const pk = kg * Math.exp(jitter(rand, noise[m]!));
        const pa = avg * Math.exp(jitter(rand, noise[m]! / 3));
        pred[m] = { kg: sig4(pk), count: Math.round(pk / pa), avg_kg: sig4(pa) };
      }
      backtest.push({ area, month, window, made_on: tenthOfNextMonth(month), actual, pred });
    }
  }

  const score = (window: 'dev' | 'holdout') => {
    const rows = backtest.filter((r) => r.window === window);
    const out: Record<string, Record<string, number | null>> = {};
    for (const [outcome, key] of [['log_kg', 'kg'], ['log_count', 'count'], ['log_avg_kg', 'avg_kg']] as const) {
      out[outcome] = {};
      for (const m of models) {
        const errs = rows.map((r) => Math.abs(Math.log(r.pred[m]![key]!) - Math.log(r.actual[key]!)));
        out[outcome]![m] = sig4(errs.reduce((a, b) => a + b, 0) / errs.length);
      }
    }
    return out;
  };

  const base = { models, windows, backtest, current: null };
  const dev = score('dev');
  if (scenario === 'pre') {
    return { ...base, scores: { dev, holdout: null, actuals: 'latest revised data, not first releases' }, f1: null, latest: null };
  }

  const holdout = score('holdout');
  const b1 = holdout.log_kg!.b1!;
  const drv = holdout.log_kg!.drivers!;
  const improvement = sig4((1 - drv / b1) * 100);
  const sept = backtest.filter((r) => r.month === '2026-09' && r.area >= 1);
  const errPct = (p: number, a: number) => sig4((p / a - 1) * 100);
  const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
  const predKg = sum(sept.map((r) => r.pred.drivers!.kg!));
  const actualKg = sum(sept.map((r) => r.actual.kg!));
  return {
    ...base,
    scores: { dev, holdout, actuals: 'latest revised data, not first releases' },
    f1: {
      window: 'holdout',
      mae_b1: b1,
      mae_drivers: drv,
      improvement_pct: improvement,
      cw_stat: 2.1,
      cw_p: 0.02,
      pass: improvement >= 5,
    },
    latest: {
      month: '2026-09',
      made_on: '2026-10-10',
      model: 'drivers',
      national: { pred_kg: sig4(predKg), actual_kg: sig4(actualKg), error_pct: errPct(predKg, actualKg) },
      areas: sept.map((r) => ({
        area: r.area,
        pred_kg: r.pred.drivers!.kg,
        actual_kg: r.actual.kg,
        error_pct: errPct(r.pred.drivers!.kg!, r.actual.kg!),
      })),
    },
  };
}

// ---- Finding 5: drivers (after the freeze only) ----

const GROUPS: { group: string; label: string; columns: string[] }[] = [
  { group: 'stock', label: 'Stock (biomass, fish numbers)', columns: ['biomass_anom', 'fish_stock_anom'] },
  { group: 'market', label: 'Market (export volume)', columns: ['export_vol_anom'] },
  { group: 'pipeline', label: 'Smolt pipeline', columns: ['smolt_pipe_anom'] },
  { group: 'feed', label: 'Feed per kg of biomass', columns: ['feed_rate_anom'] },
  { group: 'temperature', label: 'Sea temperature', columns: ['dd_below8', 'dd_8to14', 'dd_above14'] },
  { group: 'losses', label: 'Losses (deaths, disease)', columns: ['mortality_anom', 'disease_share'] },
  { group: 'lice', label: 'Lice and treatments', columns: ['mobile_anom', 'treat_anom'] },
];

function makeDrivers(rand: Rand): Drivers {
  const full = 0.15;
  const rises = [9.3, 4.1, 2.2, 1.4, 6.7, 0.8, -0.6]; // one negative, shown as it is
  return {
    outcome: 'log_kg',
    window: '2021-01 to 2026-09',
    full_mae: full,
    groups: GROUPS.map((g, i) => ({
      ...g,
      mae_without: sig4(full * (1 + rises[i]! / 100)),
      increase_pct: rises[i]!,
    })),
    by_outcome: {
      log_count: GROUPS.map((g) => ({ group: g.group, increase_pct: sig4(jitter(rand, 5) + 3) })),
      log_avg_kg: GROUPS.map((g) => ({ group: g.group, increase_pct: sig4(jitter(rand, 3) + 1) })),
    },
  };
}

// ---- Finding 7: price ----

function makePrice(scenario: MockScenario, rand: Rand): Price {
  const post = scenario === 'post';
  const history = weeksBetween('2024-W01', '2026-W44').map((week) => ({
    week,
    price_nok_kg: sig4(80 + 15 * season(weekNo(week), 52, 5) + jitter(rand, 3)),
  }));
  const windowsUsed: ('dev' | 'holdout')[] = post ? ['dev', 'holdout'] : ['dev'];
  const horizons = [2, 3, 4, 5, 6, 7, 8];
  const ratios: Record<string, number> = { rw: 1, ar: 0.99, c0: 0.97, c1: 0.96 };

  const scorecard = windowsUsed.flatMap((window) =>
    horizons.flatMap((h) =>
      Object.entries(ratios).map(([model, ratio]) => {
        const r = model === 'rw' ? 1 : sig4(ratio + jitter(rand, 0.01));
        return {
          window,
          h,
          model,
          mae: sig4((0.03 + 0.006 * h) * r),
          mae_ratio: r,
          hit_rate: model === 'rw' ? null : sig4(0.5 + rand() * 0.1),
        };
      }),
    ),
  );
  const cw = windowsUsed.flatMap((window) =>
    horizons.map((h) => ({
      window,
      h,
      stat: sig4(0.5 + rand() * 1.5),
      p: sig4(0.05 + rand() * 0.3),
      p_holm: h === 4 ? null : sig4(Math.min(1, 0.2 + rand() * 0.6)),
      primary: h === 4,
    })),
  );
  const years = post ? [2021, 2022, 2023, 2024, 2025, 2026] : [2021, 2022, 2023, 2024];
  const by_year = years.map((year) => ({ year, mae_c0: sig4(0.06 + rand() * 0.02), mae_c1: sig4(0.058 + rand() * 0.02) }));

  const priceOf = new Map(history.map((h) => [h.week, h.price_nok_kg]));
  const backtest_h4 = post
    ? weeksBetween('2025-W01', '2026-W44').map((week) => {
        const actual = priceOf.get(week) ?? null;
        const c0 = (actual ?? 80) * (1 + jitter(rand, 0.05));
        const c1 = (actual ?? 80) * (1 + jitter(rand, 0.045));
        return { week, actual, pred_c0: sig4(c0), pred_c1: sig4(c1), band_model: 'c0', p10: sig4(c0 * 0.92), p90: sig4(c0 * 1.08) };
      })
    : null;

  return {
    history,
    c1_drivers: ['mobile_anom', 'treat_anom', 'dd_below8', 'biomass_anom'],
    windows: { dev: ['2021-W01', '2024-W52'], holdout: ['2025-W01', '2026-W44'] },
    notes: ['MOCK DATA: made-up numbers for building the site, not results.'],
    scorecard,
    cw,
    by_year,
    f2: post ? { window: 'holdout', mae_c0: 0.063, mae_c1: 0.061, cw_p: 0.11, pass: false } : null,
    backtest_h4,
    current: null,
  };
}

// ---- Mock chart specs: plain Vega-Lite v5 (what Altair 5 writes), data inlined ----

const VL = 'https://vega.github.io/schema/vega-lite/v5.20.1.json';
const mockTitle = (text: string, subtitle = 'Made-up data for building the site') => ({
  text: `MOCK — ${text}`,
  subtitle,
});

function trapSpec(trap: Trap): ChartSpec {
  const corr = trap.drivers.flatMap((d) => [
    { label: d.label, kind: 'Raw', r: d.raw_r },
    { label: d.label, kind: 'Season and trend removed', r: d.anom_r },
  ]);
  const standardise = (xs: (number | null)[]) => {
    const v = xs.filter((x): x is number => x !== null);
    const m = v.reduce((a, b) => a + b, 0) / v.length;
    const sd = Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length) || 1;
    return xs.map((x) => (x === null ? null : r2((x - m) / sd)));
  };
  const dz = standardise(trap.series.map((s) => s.driver));
  const pz = standardise(trap.series.map((s) => s.price));
  const series = trap.series.flatMap((s, i) => {
    const date = isoDate(mondayOf(s.week));
    return [
      { date, line: 'Mobile lice', value: dz[i] },
      { date, line: 'Log price', value: pz[i] },
    ];
  });
  return {
    $schema: VL,
    title: mockTitle('The seasonality trap'),
    vconcat: [
      {
        width: 560,
        height: { step: 30 },
        layer: [
          {
            data: { values: [{ zero: 0 }] },
            mark: { type: 'rule', color: '#888' },
            encoding: { x: { field: 'zero', type: 'quantitative' } },
          },
          {
            data: { values: corr },
            mark: 'line',
            encoding: {
              y: { field: 'label', type: 'nominal', title: null },
              x: { field: 'r', type: 'quantitative', scale: { domain: [-1, 1] }, title: 'Correlation with log price' },
              detail: { field: 'label', type: 'nominal' },
            },
          },
          {
            data: { values: corr },
            mark: { type: 'point', filled: true, size: 90 },
            encoding: {
              y: { field: 'label', type: 'nominal' },
              x: { field: 'r', type: 'quantitative' },
              color: { field: 'kind', type: 'nominal', title: null },
            },
          },
        ],
      },
      {
        width: 560,
        height: 180,
        data: { values: series },
        mark: 'line',
        encoding: {
          x: { field: 'date', type: 'temporal', title: null },
          y: { field: 'value', type: 'quantitative', title: 'Standardised (mean 0, sd 1)' },
          color: { field: 'line', type: 'nominal', title: null },
        },
      },
    ],
  };
}

const BIN_TITLES: Record<string, string> = {
  lice: 'Mobile lice',
  temp: 'Sea temperature',
  feed: 'Feed per kg of biomass',
  mortality: 'Deaths per 1,000 fish',
};

function binsSpec(ch: Channels): ChartSpec {
  const panel = (b: Channels['bins'][number]) => `${BIN_TITLES[b.driver] ?? b.driver} (lags ${b.window})`;
  const values = ch.bins.flatMap((b) => [
    { panel: panel(b), tercile: b.tercile, measure: 'Fish count', anom: b.count_anom, n: b.n },
    { panel: panel(b), tercile: b.tercile, measure: 'Average weight', anom: b.weight_anom, n: b.n },
  ]);
  return {
    $schema: VL,
    title: mockTitle('Count and weight anomalies by tercile'),
    data: { values },
    facet: { column: { field: 'panel', type: 'nominal', title: null, sort: [...new Set(values.map((v) => v.panel))] } },
    spec: {
      width: 150,
      height: 200,
      mark: 'bar',
      encoding: {
        x: { field: 'tercile', type: 'ordinal', title: 'Tercile' },
        xOffset: { field: 'measure', type: 'nominal' },
        y: { field: 'anom', type: 'quantitative', title: 'Anomaly (log)' },
        color: { field: 'measure', type: 'nominal', title: null },
        tooltip: [
          { field: 'measure', type: 'nominal' },
          { field: 'anom', type: 'quantitative', format: '.3f' },
          { field: 'n', type: 'quantitative', title: 'Area-months' },
        ],
      },
    },
  };
}

function nowcastSpec(nc: Nowcast): ChartSpec {
  const byMonth = new Map<string, { actual: number; pred: number }>();
  for (const r of nc.backtest) {
    if (r.area < 1) continue; // national = areas 1–13
    const m = byMonth.get(r.month) ?? { actual: 0, pred: 0 };
    m.actual += r.actual.kg ?? 0;
    m.pred += r.pred.drivers?.kg ?? 0;
    byMonth.set(r.month, m);
  }
  const values = [...byMonth].flatMap(([month, v]) => [
    { month, series: 'Published', tonnes: Math.round(v.actual / 1000) },
    { month, series: 'Drivers nowcast', tonnes: Math.round(v.pred / 1000) },
  ]);
  const hasHoldout = nc.backtest.some((r) => r.window === 'holdout');
  const layer: Record<string, unknown>[] = [];
  if (hasHoldout) {
    layer.push({
      data: { values: [{ start: nc.windows.holdout[0], end: nc.windows.holdout[1] }] },
      mark: { type: 'rect', color: '#ececec' },
      encoding: { x: { field: 'start', type: 'temporal' }, x2: { field: 'end' } },
    });
  }
  layer.push({
    data: { values },
    mark: { type: 'line', point: true },
    encoding: {
      x: { field: 'month', type: 'temporal', title: null },
      y: { field: 'tonnes', type: 'quantitative', title: 'Harvest, tonnes (areas 1–13)' },
      color: { field: 'series', type: 'nominal', title: null },
    },
  });
  if (nc.latest) {
    layer.push({
      data: {
        values: [
          {
            month: nc.latest.month,
            tonnes: Math.round((nc.latest.national.actual_kg ?? 0) / 1000),
            label: `${nc.latest.month}: error ${nc.latest.national.error_pct}%`,
          },
        ],
      },
      mark: { type: 'text', dy: -16, dx: -8, align: 'right', fontWeight: 'bold' },
      encoding: {
        x: { field: 'month', type: 'temporal' },
        y: { field: 'tonnes', type: 'quantitative' },
        text: { field: 'label', type: 'nominal' },
      },
    });
  }
  return {
    $schema: VL,
    title: mockTitle('National harvest: published against the nowcast', hasHoldout ? 'Shaded: the holdout' : 'Development window only'),
    width: 'container',
    height: 280,
    layer,
  };
}

function driversSpec(d: Drivers): ChartSpec {
  return {
    $schema: VL,
    title: mockTitle('Rise in nowcast error without each driver group', 'Exploratory, no pass mark'),
    width: 'container',
    height: { step: 30 },
    data: { values: d.groups },
    layer: [
      {
        mark: 'bar',
        encoding: {
          y: { field: 'label', type: 'nominal', sort: '-x', title: null },
          x: { field: 'increase_pct', type: 'quantitative', title: 'Rise in MAE without the group (%)' },
        },
      },
      { mark: { type: 'rule', color: '#333' }, encoding: { x: { datum: 0 } } },
    ],
  };
}

function panelSpec(ch: Channels): ChartSpec {
  const values = (ch.panel ?? []).map((r) => ({
    ...r,
    row: `${r.test}: ${r.driver} → ${r.outcome} (lags ${r.lags})`,
    result: r.pass === null ? 'no pass mark' : r.pass ? 'pass' : 'fail',
  }));
  return {
    $schema: VL,
    title: mockTitle('M1 and M2: sums of lag coefficients', '95% intervals'),
    width: 'container',
    height: { step: 34 },
    data: { values },
    layer: [
      { mark: { type: 'rule', color: '#888' }, encoding: { x: { datum: 0 } } },
      {
        mark: 'rule',
        encoding: {
          y: { field: 'row', type: 'nominal', title: null, sort: null },
          x: { field: 'lo', type: 'quantitative', title: 'Coefficient sum' },
          x2: { field: 'hi' },
        },
      },
      {
        mark: { type: 'point', filled: true, size: 80 },
        encoding: {
          y: { field: 'row', type: 'nominal', sort: null },
          x: { field: 'coef_sum', type: 'quantitative' },
          color: { field: 'result', type: 'nominal', title: null },
        },
      },
    ],
  };
}

function scorecardSpec(p: Price): ChartSpec {
  return {
    $schema: VL,
    title: mockTitle('Price forecast error relative to the random walk'),
    width: 'container',
    height: 260,
    data: { values: p.scorecard },
    layer: [
      { mark: { type: 'rule', strokeDash: [4, 4] }, encoding: { y: { datum: 1 } } },
      {
        mark: { type: 'line', point: true },
        encoding: {
          x: { field: 'h', type: 'ordinal', title: 'Weeks ahead' },
          y: { field: 'mae_ratio', type: 'quantitative', scale: { zero: false }, title: 'MAE ÷ random-walk MAE' },
          color: { field: 'model', type: 'nominal', title: 'Model' },
          strokeDash: { field: 'window', type: 'nominal', title: 'Window' },
        },
      },
    ],
  };
}

function byYearSpec(p: Price): ChartSpec {
  const values = p.by_year.flatMap((r) => [
    { year: String(r.year), model: 'c0', mae: r.mae_c0 },
    { year: String(r.year), model: 'c1', mae: r.mae_c1 },
  ]);
  return {
    $schema: VL,
    title: mockTitle('c0 against c1 error by year, 4 weeks ahead'),
    width: 'container',
    height: 240,
    data: { values },
    mark: 'bar',
    encoding: {
      x: { field: 'year', type: 'ordinal', title: null },
      xOffset: { field: 'model', type: 'nominal' },
      y: { field: 'mae', type: 'quantitative', title: 'MAE (log price)' },
      color: { field: 'model', type: 'nominal', title: 'Model' },
    },
  };
}

function priceBacktestSpec(p: Price): ChartSpec {
  const rows = (p.backtest_h4 ?? []).map((r) => ({ ...r, date: isoDate(mondayOf(r.week)) }));
  const lines = rows.flatMap((r) => [
    { date: r.date, series: 'Actual', nok: r.actual },
    { date: r.date, series: 'c0 forecast', nok: r.pred_c0 },
    { date: r.date, series: 'c1 forecast', nok: r.pred_c1 },
  ]);
  return {
    $schema: VL,
    title: mockTitle('Holdout: actual price against 4-week-ahead forecasts', '80% band'),
    width: 'container',
    height: 280,
    layer: [
      {
        data: { values: rows },
        mark: { type: 'area', opacity: 0.2 },
        encoding: {
          x: { field: 'date', type: 'temporal', title: null },
          y: { field: 'p10', type: 'quantitative', title: 'NOK per kg' },
          y2: { field: 'p90' },
        },
      },
      {
        data: { values: lines },
        mark: 'line',
        encoding: {
          x: { field: 'date', type: 'temporal' },
          y: { field: 'nok', type: 'quantitative' },
          color: { field: 'series', type: 'nominal', title: null },
        },
      },
    ],
  };
}

// ---- The final harvest forecast: only exists after the freeze ----

/** The forecast for the month after the backtest ends, from the backtest's last month. */
function makeFarmerActions(combined: Combined): FarmerActions {
  const last = combined.backtest.reduce((newest, r) => (r.month > newest ? r.month : newest), '');
  const rows = combined.backtest.filter((r) => r.month === last).sort((a, b) => a.area - b.area);
  return {
    made_on: '2026-11-08',
    target_month: '2026-10',
    publishes_around: '2026-11-20',
    national: { areas: rows.map((r) => r.area), kg: rows.reduce((sum, r) => sum + (r.pred.kg ?? 0), 0) },
    areas: rows.map((r, i) => ({
      area: r.area,
      name: `Mock area ${r.area}`,
      forecast: { kg: r.pred.kg, kg_range: [Math.round((r.pred.kg ?? 0) * 0.7), Math.round((r.pred.kg ?? 0) * 1.35)] },
      vs_last_year_pct: i % 2 ? 6 : -9,
    })),
  };
}

function makeCombined(nowcast: Nowcast): Combined {
  const rand = seeded(41); // its own seed, so the other mock files don't change
  const noise: Record<string, number> = { ml: 0.11, blend: 0.1, combined: 0.08 };
  const rows = nowcast.backtest
    .filter((r) => r.area >= 2 && r.area <= 12)
    .map((r) => {
      const pred: Record<string, KCW> = { b1: r.pred.b1!, drivers: r.pred.drivers! };
      for (const [model, size] of Object.entries(noise)) {
        const pk = r.actual.kg! * Math.exp(jitter(rand, size));
        const pa = r.actual.avg_kg! * Math.exp(jitter(rand, size / 3));
        pred[model] = { kg: sig4(pk), count: Math.round(pk / pa), avg_kg: sig4(pa) };
      }
      return { ...r, pred };
    });

  const score = (window: 'dev' | 'holdout') => {
    const part = rows.filter((r) => r.window === window);
    const mae = (model: string, key: 'kg' | 'count' | 'avg_kg') =>
      sig4(part.reduce((sum, r) => sum + Math.abs(Math.log(r.pred[model]![key]!) - Math.log(r.actual[key]!)), 0) / part.length);
    const row = (key: 'kg' | 'count' | 'avg_kg') => ({
      n: part.length,
      b1: mae('b1', key),
      drivers: mae('drivers', key),
      ml: mae('ml', key),
      blend: mae('blend', key),
      combined: mae('combined', key),
    });
    return { log_kg: row('kg'), log_count: row('count'), log_avg_kg: row('avg_kg') };
  };

  return {
    windows: nowcast.windows,
    scores: { dev: score('dev'), holdout: score('holdout') },
    backtest: rows.map(({ area, month, window, actual, pred }) => ({ area, month, window, actual, pred: pred.combined! })),
  };
}

// ---- Putting a scenario together ----

/** Every mock file for one scenario, keyed by its path inside _mock/<scenario>/. */
export function buildScenario(scenario: MockScenario): Record<string, unknown> {
  const rand = seeded(scenario === 'pre' ? 7 : 8);
  const farms = makeFarms(seeded(1));
  const index: FarmWeeksIndex = { years: [2025, 2026] };
  const trap = makeTrap(rand);
  const channels = makeChannels(scenario, rand);
  const nowcast = makeNowcast(scenario, rand);
  const price = makePrice(scenario, rand);

  // Disease flags are optional: present in "post", left out of "pre", to test both.
  const withDisease = scenario === 'post';
  const files: Record<string, unknown> = {
    'farms.json': farms,
    'farm_weeks/index.json': index,
    'farm_weeks/2025.json': makeFarmYear(2025, weeksBetween('2025-W01', '2025-W52'), farms, withDisease, seeded(2025)),
    'farm_weeks/2026.json': makeFarmYear(2026, weeksBetween('2026-W01', '2026-W44'), farms, withDisease, seeded(2026)),
    'area_month.json': makeAreaMonth(rand),
    'trap.json': trap,
    'channels.json': channels,
    'nowcast.json': nowcast,
    'price.json': price,
    'charts/trap.vl.json': trapSpec(trap),
    'charts/channels_bins.vl.json': binsSpec(channels),
    'charts/nowcast_backtest.vl.json': nowcastSpec(nowcast),
  };
  if (scenario === 'post') {
    const drivers = makeDrivers(rand);
    const combined = makeCombined(nowcast);
    Object.assign(files, {
      'combined.json': combined,
      'farmer_actions.json': makeFarmerActions(combined),
      'drivers.json': drivers,
      'charts/drivers_importance.vl.json': driversSpec(drivers),
      'charts/channels_panel.vl.json': panelSpec(channels),
      'charts/price_scorecard.vl.json': scorecardSpec(price),
      'charts/price_by_year.vl.json': byYearSpec(price),
      'charts/price_backtest.vl.json': priceBacktestSpec(price),
    });
  }
  // price_fan.vl.json is optional and left out of both, to test that state.
  return files;
}
