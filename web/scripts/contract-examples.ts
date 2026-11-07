// The example JSON from docs/plans/00-shared.md, copied as written. The checks
// confirm every example passes its schema, so the schemas follow the contract
// rather than just our own mocks. If 00-shared.md changes, update these.

export const farms = [{ id: 12345, name: 'Example site', lat: 63.1, lon: 8.2, area: 6, capacity_t: 3120 }];

export const farmWeeksIndex = { years: [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026] };

export const farmWeeksYear = {
  year: 2024,
  weeks: ['2024-W01', '2024-W02'],
  ids: [12345, 23456],
  mobile: [
    [0.42, null],
    [0.51, 0.08],
  ],
  treated: [
    [0, null],
    [1, 0],
  ],
  disease: [
    [0, null],
    [0, 1],
  ],
  temp: [
    [7.85, null],
    [7.6, 6.9],
  ],
};

export const areaMonth = [
  {
    area: 6,
    month: '2024-09',
    kg: 17700000,
    count: 4100000,
    avg_kg: 4.31,
    volume_anom: 0.07,
    count_anom: 0.12,
    weight_anom: -0.05,
    mobile_idx: 0.61,
    dd_anom: 14.2,
    feed_rate_anom: 0.03,
    mortality_anom: 0.1,
  },
];

export const trap = {
  from: '2017-W01',
  to: '2026-W44',
  highlight: 'mobile_idx',
  drivers: [
    { driver: 'mobile_idx', label: 'Mobile lice per fish', raw_r: -0.6, anom_r: -0.1 },
    { driver: 'temp_c', label: 'Sea temperature', raw_r: -0.7, anom_r: 0.05 },
  ],
  series: [{ week: '2024-W36', driver: 0.9, price: 4.2, driver_anom: 0.1, price_anom: -0.03 }],
};

export const channels = {
  bins: [{ driver: 'lice', tercile: 3, window: '0-3', count_anom: 0.04, weight_anom: -0.02, n: 310 }],
  panel: [
    {
      test: 'M1',
      outcome: 'log_count',
      driver: 'mobile_lice',
      lags: '0-3',
      coef_sum: 0.03,
      lo: 0.01,
      hi: 0.05,
      pass: true,
    },
  ],
};

export const nowcastBeforeFreeze = {
  models: ['b0', 'b1', 'drivers'],
  windows: { dev: ['2021-01', '2024-12'], holdout: ['2025-01', '2026-09'] },
  backtest: [
    {
      area: 6,
      month: '2024-09',
      window: 'dev',
      made_on: '2024-10-10',
      actual: { kg: 17700000, count: 4100000, avg_kg: 4.31 },
      pred: {
        b0: { kg: 16900000, count: 3900000, avg_kg: 4.5 },
        b1: { kg: 17200000, count: 4000000, avg_kg: 4.45 },
        drivers: { kg: 17500000, count: 4050000, avg_kg: 4.36 },
      },
    },
  ],
  scores: {
    dev: {
      log_kg: { b0: 0.2, b1: 0.17, drivers: 0.15 },
      log_count: { b0: 0.21, b1: 0.18, drivers: 0.17 },
      log_avg_kg: { b0: 0.06, b1: 0.06, drivers: 0.05 },
    },
    holdout: null,
    actuals: 'latest revised data, not first releases',
  },
  f1: null,
  latest: null,
  current: null,
};

export const nowcastAfterFreeze = {
  ...nowcastBeforeFreeze,
  f1: {
    window: 'holdout',
    mae_b1: 0.17,
    mae_drivers: 0.15,
    improvement_pct: 11.8,
    cw_stat: 2.1,
    cw_p: 0.02,
    pass: true,
  },
  latest: {
    month: '2026-09',
    made_on: '2026-10-10',
    model: 'drivers',
    national: { pred_kg: 180000000, actual_kg: 184000000, error_pct: -2.2 },
    areas: [{ area: 6, pred_kg: 17500000, actual_kg: 17700000, error_pct: -1.1 }],
  },
};

export const drivers = {
  outcome: 'log_kg',
  window: '2021-01 to 2026-09',
  full_mae: 0.15,
  groups: [
    {
      group: 'lice',
      label: 'Lice and treatments',
      columns: ['mobile_anom', 'treat_anom'],
      mae_without: 0.16,
      increase_pct: 6.7,
    },
  ],
  by_outcome: {
    log_count: [{ group: 'lice', increase_pct: 8.0 }],
    log_avg_kg: [{ group: 'lice', increase_pct: 3.1 }],
  },
};

export const priceBeforeFreeze = {
  history: [{ week: '2026-W44', price_nok_kg: 70.0 }],
  c1_drivers: ['mobile_anom', 'treat_anom', 'dd_below8', 'biomass_anom'],
  windows: { dev: ['2021-W01', '2024-W52'], holdout: ['2025-W01', '2026-W44'] },
  notes: ['disease_share dropped from c1: no disease flags in BarentsWatch'],
  scorecard: [{ window: 'dev', h: 4, model: 'c1', mae: 0.06, mae_ratio: 0.97, hit_rate: 0.55 }],
  cw: [{ window: 'dev', h: 4, stat: 1.2, p: 0.11, p_holm: null, primary: true }],
  by_year: [{ year: 2024, mae_c0: 0.07, mae_c1: 0.068 }],
  f2: null,
  backtest_h4: null,
  current: null,
};

export const priceAfterFreeze = {
  ...priceBeforeFreeze,
  f2: { window: 'holdout', mae_c0: 0.063, mae_c1: 0.061, cw_p: 0.11, pass: false },
  backtest_h4: [
    { week: '2025-W10', actual: 85.0, pred_c0: 83.0, pred_c1: 84.0, band_model: 'c0', p10: 78.0, p90: 90.0 },
  ],
};
