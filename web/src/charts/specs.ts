// Vega-Lite specs for the charts the site draws from the published data, in
// the site's own style. Colours checked with the dataviz palette validator on
// white: blue and coral ΔE 17 for colour-blind readers, each at least 3:1.

import { fmtMonth } from '../components/format';
import type { AreaMonth, ChartSpec, Combined, Price } from '../data/schemas';

export const BLUE = '#2f6fa7';
export const CORAL = '#d0603a';
export const PURPLE = '#6f56b8';

const SCHEMA = 'https://vega.github.io/schema/vega-lite/v6.json';
const INK = '#142130';
const INK_2 = '#4b5664';
const INK_3 = '#5d6773';

const CONFIG = {
  font: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  background: 'transparent',
  view: { stroke: null },
  axis: {
    labelFontSize: 12,
    titleFontSize: 12,
    titleFontWeight: 500,
    labelColor: INK_2,
    titleColor: INK_2,
    gridColor: '#eceeec',
    domainColor: '#c9cfd4',
    tickColor: '#c9cfd4',
    labelPadding: 6,
    titlePadding: 10,
  },
  legend: { labelFontSize: 13, labelColor: INK, labelLimit: 320, orient: 'top', title: null, symbolStrokeWidth: 2.5, offset: 12 },
};

const FILL_WIDTH = { width: 'container', autosize: { type: 'fit-x', contains: 'padding' } };

/** A date Vega reads in the visitor's own time zone, so months never slip. */
const monthDate = (month: string) => `${month}-01T00:00:00`;

export type MonthTotal = { month: string; forecast: number; published: number; window: 'dev' | 'holdout' };

/** Each month's forecast and published harvest, added up over the areas forecast. */
export function monthlyTotals(c: Combined): MonthTotal[] {
  const months = new Map<string, MonthTotal & { areas: number }>();
  for (const r of c.backtest) {
    if (r.pred.kg === null || r.actual.kg === null) continue;
    const m = months.get(r.month) ?? { month: r.month, forecast: 0, published: 0, window: r.window, areas: 0 };
    m.forecast += r.pred.kg;
    m.published += r.actual.kg;
    m.areas += 1;
    months.set(r.month, m);
  }
  // A month missing some areas would look like a dip, so only full months count.
  const full = Math.max(0, ...[...months.values()].map((m) => m.areas));
  return [...months.values()].filter((m) => m.areas === full).sort((a, b) => a.month.localeCompare(b.month));
}

export function forecastSpec(c: Combined): ChartSpec {
  const totals = monthlyTotals(c);
  const values = totals.flatMap((t) =>
    (
      [
        ['Published', t.published],
        ['Our forecast', t.forecast],
      ] as const
    ).map(([series, kg]) => ({ date: monthDate(t.month), label: fmtMonth(t.month), series, tonnes: kg / 1000 })),
  );
  const test = totals.filter((t) => t.window === 'holdout');
  const band = test.length ? [{ from: monthDate(test[0]!.month), to: monthDate(test[test.length - 1]!.month) }] : [];
  const x = { field: 'date', type: 'temporal' };
  const y = { field: 'tonnes', type: 'quantitative' };
  const color = { field: 'series', type: 'nominal', scale: { domain: ['Published', 'Our forecast'], range: [BLUE, CORAL] } };
  return {
    $schema: SCHEMA,
    ...FILL_WIDTH,
    height: 320,
    config: CONFIG,
    data: { values },
    layer: [
      {
        data: { values: band },
        mark: { type: 'rect', color: '#eef1ee' },
        encoding: { x: { field: 'from', type: 'temporal' }, x2: { field: 'to' } },
      },
      {
        data: { values: band },
        mark: { type: 'text', align: 'left', baseline: 'top', dx: 10, dy: 10, color: INK_3, fontSize: 12 },
        encoding: { x: { field: 'from', type: 'temporal' }, y: { value: 0 }, text: { value: 'Months the model never saw' } },
      },
      {
        mark: { type: 'line', strokeWidth: 2.25 },
        encoding: {
          x: { ...x, title: null, axis: { format: '%Y', tickCount: 'year', grid: false } },
          y: { ...y, title: 'Tonnes harvested in the month', scale: { zero: false }, axis: { format: ',.0f', tickCount: 5 } },
          color,
        },
      },
      {
        mark: { type: 'circle', size: 60 },
        encoding: { x, y, color, opacity: { condition: { param: 'hover', empty: false, value: 1 }, value: 0 } },
      },
      {
        transform: [{ pivot: 'series', value: 'tonnes', groupby: ['date', 'label'] }],
        mark: { type: 'rule', color: INK, strokeWidth: 1 },
        encoding: {
          x,
          opacity: { condition: { param: 'hover', empty: false, value: 0.35 }, value: 0 },
          tooltip: [
            { field: 'label', title: 'Month' },
            { field: 'Published', type: 'quantitative', format: ',.0f', title: 'Published (t)' },
            { field: 'Our forecast', type: 'quantitative', format: ',.0f', title: 'Our forecast (t)' },
          ],
        },
        params: [{ name: 'hover', select: { type: 'point', fields: ['date'], nearest: true, on: 'pointerover', clear: 'pointerout' } }],
      },
    ],
  };
}

export const PRICE_MODELS: Record<string, string> = {
  ar: 'Past prices only',
  c0: 'Prices and market data',
  c1: 'Prices, market and farm data',
};

/** The test weeks once they've been scored; until then, the years the models were built on. */
export const priceWindow = (p: Price): 'dev' | 'holdout' => (p.scorecard.some((r) => r.window === 'holdout') ? 'holdout' : 'dev');

export function scorecardSpec(p: Price): ChartSpec {
  const window = priceWindow(p);
  const values = p.scorecard.flatMap((r) => {
    const model = PRICE_MODELS[r.model];
    return r.window === window && model && r.mae_ratio !== null ? [{ weeks: r.h, ratio: r.mae_ratio, model }] : [];
  });
  return {
    $schema: SCHEMA,
    ...FILL_WIDTH,
    height: 280,
    config: CONFIG,
    data: { values },
    layer: [
      { mark: { type: 'rule', color: INK_3, strokeDash: [4, 4] }, encoding: { y: { datum: 1 } } },
      {
        mark: { type: 'text', align: 'right', baseline: 'bottom', dy: -5, color: INK_3, fontSize: 12 },
        encoding: { x: { value: 'width' }, y: { datum: 1 }, text: { value: 'Random walk' } },
      },
      {
        mark: { type: 'line', strokeWidth: 2.25, point: { size: 56, filled: true } },
        encoding: {
          x: { field: 'weeks', type: 'ordinal', title: 'Weeks ahead', axis: { labelAngle: 0, grid: false } },
          y: { field: 'ratio', type: 'quantitative', title: 'Error compared with a random walk', scale: { zero: false }, axis: { format: '.1f', tickCount: 5 } },
          color: {
            field: 'model',
            type: 'nominal',
            scale: { domain: Object.values(PRICE_MODELS), range: [PURPLE, BLUE, CORAL] },
            legend: { columns: 1, symbolType: 'stroke' },
          },
          tooltip: [
            { field: 'model', title: 'Model' },
            { field: 'weeks', title: 'Weeks ahead' },
            { field: 'ratio', type: 'quantitative', format: '.2f', title: 'Versus random walk' },
          ],
        },
      },
    ],
  };
}

export function priceByYearSpec(p: Price): ChartSpec {
  const c0 = PRICE_MODELS.c0!;
  const c1 = PRICE_MODELS.c1!;
  const values = p.by_year.flatMap((y) => [
    { year: y.year, model: c0, error: y.mae_c0 },
    { year: y.year, model: c1, error: y.mae_c1 },
  ]);
  return {
    $schema: SCHEMA,
    ...FILL_WIDTH,
    height: 280,
    config: CONFIG,
    data: { values },
    mark: { type: 'bar', cornerRadiusEnd: 4 },
    encoding: {
      x: { field: 'year', type: 'ordinal', title: null, axis: { labelAngle: 0, grid: false }, scale: { paddingInner: 0.3 } },
      xOffset: { field: 'model', scale: { paddingInner: 0.08 } },
      y: { field: 'error', type: 'quantitative', title: 'Typical error, four weeks ahead', axis: { format: '.2f', tickCount: 5 } },
      color: { field: 'model', type: 'nominal', scale: { domain: [c0, c1], range: [BLUE, CORAL] }, legend: { columns: 1 } },
      tooltip: [
        { field: 'year', title: 'Year' },
        { field: 'model', title: 'Model' },
        { field: 'error', type: 'quantitative', format: '.3f', title: 'Typical error' },
      ],
    },
  };
}

export function areaHeatSpec(rows: AreaMonth): ChartSpec {
  const values = rows.flatMap((r) =>
    r.kg === null || r.area < 1 ? [] : [{ date: monthDate(r.month), label: fmtMonth(r.month), area: r.area, tonnes: r.kg / 1000 }],
  );
  return {
    $schema: SCHEMA,
    ...FILL_WIDTH,
    height: 260,
    config: CONFIG,
    data: { values },
    mark: { type: 'rect' },
    encoding: {
      x: { field: 'date', type: 'temporal', timeUnit: 'yearmonth', title: null, axis: { format: '%Y', tickCount: 'year', grid: false, domain: false } },
      y: { field: 'area', type: 'ordinal', title: 'Production area, north at the top', sort: 'descending', axis: { ticks: false, domain: false, grid: false } },
      color: {
        field: 'tonnes',
        type: 'quantitative',
        scale: { type: 'sqrt', range: ['#fbeee7', '#eaa98e', CORAL, '#6f2a16'] },
        legend: { title: 'Tonnes harvested', titleFontSize: 12, titleColor: INK_2, gradientLength: 200, gradientThickness: 10, format: ',.0f', tickCount: 4, direction: 'horizontal', titleOrient: 'left' },
      },
      tooltip: [
        { field: 'label', title: 'Month' },
        { field: 'area', title: 'Area' },
        { field: 'tonnes', type: 'quantitative', format: ',.0f', title: 'Tonnes' },
      ],
    },
  };
}
