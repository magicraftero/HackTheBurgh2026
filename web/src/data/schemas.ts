import { z } from 'zod';

// One schema per findings file, following docs/plans/00-shared.md, which wins
// if this file ever disagrees with it.
//
// Rules taken from the contract:
// - any measured number can be null;
// - IDs, areas, years, weeks and months are never null;
// - keys the contract shows are required, unless it says they're optional;
// - extra keys are ignored, so the back end can add fields without breaking us.
// A file that fails these checks is shown as "coming later", and the scaffold
// page lists the problems so they can be reported to the file's owner.

const num = z.number().nullable();
const int = z.number().int();
const area = int.min(0).max(13);
const week = z.string().regex(/^\d{4}-W\d{2}$/, 'expected an ISO week like 2026-W44');
const month = z.string().regex(/^\d{4}-\d{2}$/, 'expected a month like 2026-09');
const day = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'expected a date like 2026-10-10');
const windowName = z.enum(['dev', 'holdout']);
const flag = z.union([z.literal(0), z.literal(1)]).nullable();

// ---- Finding 1: farm by farm, week by week (Data) ----

export const FarmsSchema = z.array(
  z.object({
    id: int,
    name: z.string(),
    lat: num,
    lon: num,
    area: int.min(1).max(13),
    capacity_t: num,
  }),
);

export const FarmWeeksIndexSchema = z.object({ years: z.array(int) });

// mobile[i][j] is week weeks[i] at farm ids[j]; null means no report.
export const FarmWeeksYearSchema = z
  .object({
    year: int,
    weeks: z.array(week),
    ids: z.array(int),
    mobile: z.array(z.array(num)),
    treated: z.array(z.array(flag)),
    disease: z.array(z.array(flag)).optional(),
    temp: z.array(z.array(num)),
  })
  .superRefine((d, ctx) => {
    for (const key of ['mobile', 'treated', 'disease', 'temp'] as const) {
      const rows = d[key];
      if (!rows) continue;
      if (rows.length !== d.weeks.length) {
        ctx.addIssue({
          code: 'custom',
          path: [key],
          message: `has ${rows.length} rows, but there are ${d.weeks.length} weeks`,
        });
      }
      const bad = rows.findIndex((row) => row.length !== d.ids.length);
      if (bad >= 0) {
        ctx.addIssue({
          code: 'custom',
          path: [key, bad],
          message: `has ${rows[bad]!.length} values, but there are ${d.ids.length} farms`,
        });
      }
    }
  });

// ---- Harvest and drivers by area and month (Production) ----

export const AreaMonthSchema = z.array(
  z.object({
    area,
    month,
    kg: num,
    count: num,
    avg_kg: num,
    volume_anom: num,
    count_anom: num,
    weight_anom: num,
    mobile_idx: num,
    dd_anom: num,
    feed_rate_anom: num,
    mortality_anom: num,
  }),
);

// ---- Finding 2: the seasonality trap (Production) ----

export const TrapSchema = z.object({
  from: week,
  to: week,
  highlight: z.string(),
  drivers: z.array(z.object({ driver: z.string(), label: z.string(), raw_r: num, anom_r: num })),
  series: z.array(
    z.object({ week, driver: num, price: num, driver_anom: num, price_anom: num }),
  ),
});

// ---- Findings 3 and 6: count x weight split, M1 and M2 (Production) ----

export const ChannelsSchema = z.object({
  bins: z.array(
    z.object({
      driver: z.string(),
      tercile: int.min(1).max(3),
      window: z.string(),
      count_anom: num,
      weight_anom: num,
      n: num,
    }),
  ),
  // Arrives at the 04:00 freeze. Missing (or null) means "coming later".
  panel: z
    .array(
      z.object({
        test: z.string(),
        outcome: z.string(),
        driver: z.string(),
        lags: z.string(),
        coef_sum: num,
        lo: num,
        hi: num,
        pass: z.boolean().nullable(), // null: reported without a pass mark
      }),
    )
    .nullish(),
});

// ---- Finding 4: production nowcast backtest, F1, the worked example ----

const kgCountWeight = z.object({ kg: num, count: num, avg_kg: num });
// outcome (log_kg, log_count, log_avg_kg) -> model (b0, b1, drivers) -> MAE
const scoreTable = z.record(z.string(), z.record(z.string(), num));

export const NowcastSchema = z.object({
  models: z.array(z.string()),
  windows: z.object({ dev: z.tuple([month, month]), holdout: z.tuple([month, month]) }),
  backtest: z.array(
    z.object({
      area,
      month,
      window: windowName,
      made_on: day,
      actual: kgCountWeight,
      pred: z.record(z.string(), kgCountWeight),
    }),
  ),
  scores: z.object({
    dev: scoreTable,
    holdout: scoreTable.nullable(), // null before the 04:00 freeze
    actuals: z.string(),
  }),
  // null before the 04:00 freeze
  f1: z
    .object({
      window: z.literal('holdout'),
      mae_b1: num,
      mae_drivers: num,
      improvement_pct: num,
      cw_stat: num,
      cw_p: num,
      pass: z.boolean(),
    })
    .nullable(),
  // The worked example (the newest published month); null before the freeze
  latest: z
    .object({
      month,
      made_on: day,
      model: z.string(),
      national: z.object({ pred_kg: num, actual_kg: num, error_pct: num }),
      areas: z.array(z.object({ area, pred_kg: num, actual_kg: num, error_pct: num })),
    })
    .nullable(),
  // Optional (Tier 3). 00-shared.md doesn't define its shape yet.
  current: z.unknown(),
});

// ---- Finding 4: the final harvest forecast (Production) ----
// Written by analysis/combined.py. It came after 00-shared.md, so the contract doesn't list it.

const combinedScore = z.object({ n: int, b1: num, drivers: num, ml: num, blend: num, combined: num }).nullable();
const combinedScores = z.object({ log_kg: combinedScore, log_count: combinedScore, log_avg_kg: combinedScore });

export const CombinedSchema = z.object({
  windows: z.object({ dev: z.tuple([month, month]), holdout: z.tuple([month, month]) }),
  scores: z.object({ dev: combinedScores, holdout: combinedScores }),
  backtest: z.array(z.object({ area, month, window: windowName, actual: kgCountWeight, pred: kgCountWeight })),
});

// ---- Finding 5: driver ranking (Production, 04:00) ----

export const DriversSchema = z.object({
  outcome: z.string(),
  window: z.string(),
  full_mae: num,
  groups: z.array(
    z.object({
      group: z.string(),
      label: z.string(),
      columns: z.array(z.string()),
      mae_without: num,
      increase_pct: num,
    }),
  ),
  by_outcome: z.record(z.string(), z.array(z.object({ group: z.string(), increase_pct: num }))),
});

// ---- Finding 7: price backtest and F2 (Price) ----

export const PriceSchema = z.object({
  history: z.array(z.object({ week, price_nok_kg: num })),
  c1_drivers: z.array(z.string()),
  windows: z.object({ dev: z.tuple([week, week]), holdout: z.tuple([week, week]) }),
  notes: z.array(z.string()),
  scorecard: z.array(
    z.object({
      window: windowName,
      h: int,
      model: z.string(),
      mae: num,
      mae_ratio: num,
      hit_rate: num,
    }),
  ),
  cw: z.array(
    z.object({ window: windowName, h: int, stat: num, p: num, p_holm: num, primary: z.boolean() }),
  ),
  by_year: z.array(z.object({ year: int, mae_c0: num, mae_c1: num })),
  // null before the 04:00 freeze
  f2: z
    .object({
      window: z.literal('holdout'),
      mae_c0: num,
      mae_c1: num,
      cw_p: num,
      pass: z.boolean(),
    })
    .nullable(),
  // null before the 04:00 freeze
  backtest_h4: z
    .array(
      z.object({
        week,
        actual: num,
        pred_c0: num,
        pred_c1: num,
        band_model: z.string(),
        p10: num,
        p90: num,
      }),
    )
    .nullable(),
  // Optional (Tier 3). 00-shared.md doesn't define its shape yet.
  current: z.unknown(),
});

// ---- Chart specs (web/public/charts/*.vl.json) ----

export const ChartSpecSchema = z
  .record(z.string(), z.unknown())
  .refine((spec) => typeof spec.$schema === 'string' && spec.$schema.includes('vega'), {
    message: 'expected a Vega-Lite spec with a "$schema" key',
  });

export type Farms = z.infer<typeof FarmsSchema>;
export type Farm = Farms[number];
export type FarmWeeksIndex = z.infer<typeof FarmWeeksIndexSchema>;
export type FarmWeeksYear = z.infer<typeof FarmWeeksYearSchema>;
export type AreaMonth = z.infer<typeof AreaMonthSchema>;
export type Trap = z.infer<typeof TrapSchema>;
export type Channels = z.infer<typeof ChannelsSchema>;
export type Nowcast = z.infer<typeof NowcastSchema>;
export type Combined = z.infer<typeof CombinedSchema>;

// ---- Finding 8: the forecast for the latest month (Production) ----
// Written by analysis/farmer.py. Only the parts the site shows are checked.

export const FarmerActionsSchema = z.object({
  made_on: day,
  target_month: month,
  publishes_around: day,
  national: z.object({ areas: z.array(area), kg: num }),
  areas: z.array(
    z.object({
      area,
      name: z.string(),
      forecast: z.object({ kg: num, kg_range: z.tuple([num, num]) }).nullable(),
      vs_last_year_pct: num,
    }),
  ),
});

export type FarmerActions = z.infer<typeof FarmerActionsSchema>;
export type Drivers = z.infer<typeof DriversSchema>;
export type Price = z.infer<typeof PriceSchema>;
export type ChartSpec = z.infer<typeof ChartSpecSchema>;
