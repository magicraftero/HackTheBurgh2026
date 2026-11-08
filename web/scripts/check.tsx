// Checks the front end without a browser. Run with: npm run check
//
// 1. The contract's own examples (00-shared.md) pass the schemas.
// 2. The mocks pass, with the right before- and after-freeze shapes.
// 3. The loader turns every kind of server answer into the right state.
// 4. Every mock chart compiles and draws with Vega.
// 5. The page renders in every scenario, including a broken file.
// 6. The farm map: coastline file, projection, week dates, names, colour bins,
//    the heat's values and the year strip's area averages.

import { renderToString } from 'react-dom/server';
import * as vega from 'vega';
import { compile } from 'vega-lite';
import type { z } from 'zod';
import { App } from '../src/App';
import { CHART_NAMES, DATA_FILES, DATA_KEYS } from '../src/data/files';
import { loadJson, parseJson, type Status } from '../src/data/load';
import {
  AreaMonthSchema,
  ChannelsSchema,
  ChartSpecSchema,
  DriversSchema,
  FarmsSchema,
  FarmWeeksIndexSchema,
  FarmWeeksYearSchema,
  NowcastSchema,
  PriceSchema,
  TrapSchema,
  type ChartSpec,
} from '../src/data/schemas';
import type { AllFiles } from '../src/data/source';
import { BasemapSchema } from '../src/map/basemap';
import { VIEW, project } from '../src/map/projection';
import {
  FLAGGED_SHARE_BREAKS,
  LAYERS,
  LICE_BREAKS,
  TEMP_BREAKS,
  TEMP_COLORS,
  TREATED_SHARE_BREAKS,
  binIndex,
  heatValue,
  markFor,
} from '../src/map/scales';
import { displayName, searchKey, weekDates } from '../src/map/text';
import { AREAS_NORTH_FIRST, areaWeeks } from '../src/map/YearStrip';
import { logToPct } from '../src/charts/Figures';
import { areaHeatSpec, forecastSpec, monthlyTotals, priceByYearSpec, scorecardSpec } from '../src/charts/specs';
import { FarmExplorer, indexOfWeek } from '../src/page/FarmWeeks';
import { SitePage } from '../src/page/SitePage';
import * as ex from './contract-examples';
import type { IO } from './io';

const MOCK = 'public/data/_mock';
let failures = 0;

const heading = (t: string) => console.log(`\n${t}`);
function expect(cond: boolean, msg: string, detail?: string) {
  if (cond) console.log(`  ✓ ${msg}`);
  else {
    failures += 1;
    console.log(`  ✕ ${msg}${detail ? `: ${detail}` : ''}`);
  }
}
const describe = (s: Status<unknown>) =>
  s.state === 'invalid' ? s.problems.join('; ') : s.state === 'error' ? s.message : s.state;

function fromDisk<T>(io: IO, path: string, schema: z.ZodType<T>): Status<T> {
  const text = io.read(path);
  return text === null ? { state: 'missing', url: path } : parseJson(path, text, schema);
}

function filesIn(io: IO, dir: string): AllFiles {
  const data = Object.fromEntries(
    DATA_KEYS.map((k) => [
      k,
      fromDisk(io, `${dir}/${DATA_FILES[k].path.replace(/^data\//, '')}`, DATA_FILES[k].schema as z.ZodType<unknown>),
    ]),
  ) as AllFiles['data'];
  const charts = Object.fromEntries(
    CHART_NAMES.map((c) => [c, fromDisk(io, `${dir}/charts/${c}.vl.json`, ChartSpecSchema)]),
  ) as AllFiles['charts'];
  return { data, charts };
}

/** Rendered HTML as plain text, for "does the page say X" checks. */
const textOf = (html: string) =>
  html
    .replace(/<!-- -->/g, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ');

async function drawChart(spec: ChartSpec): Promise<{ svg: string; warnings: string[]; errors: string[] }> {
  const warnings: string[] = [];
  const errors: string[] = [];
  const { warn, error } = console;
  console.warn = (...a: unknown[]) => void warnings.push(a.map(String).join(' '));
  console.error = (...a: unknown[]) => void errors.push(a.map(String).join(' '));
  try {
    const vg = compile(spec as never).spec;
    const view = new vega.View(vega.parse(vg), { renderer: 'none' });
    const svg = await view.toSVG();
    view.finalize();
    return { svg, warnings, errors };
  } finally {
    console.warn = warn;
    console.error = error;
  }
}

export default async function main(io: IO): Promise<number> {
  // ---- 1 ----
  heading('1. The examples in 00-shared.md pass the format checks');
  const examples: [string, unknown, z.ZodType<unknown>][] = [
    ['farms.json', ex.farms, FarmsSchema],
    ['farm_weeks/index.json', ex.farmWeeksIndex, FarmWeeksIndexSchema],
    ['farm_weeks/{year}.json', ex.farmWeeksYear, FarmWeeksYearSchema],
    ['area_month.json', ex.areaMonth, AreaMonthSchema],
    ['trap.json', ex.trap, TrapSchema],
    ['channels.json', ex.channels, ChannelsSchema],
    ['channels.json without panel', { bins: ex.channels.bins }, ChannelsSchema],
    ['nowcast.json before the freeze', ex.nowcastBeforeFreeze, NowcastSchema],
    ['nowcast.json after the freeze', ex.nowcastAfterFreeze, NowcastSchema],
    ['drivers.json', ex.drivers, DriversSchema],
    ['price.json before the freeze', ex.priceBeforeFreeze, PriceSchema],
    ['price.json after the freeze', ex.priceAfterFreeze, PriceSchema],
  ];
  for (const [name, value, schema] of examples) {
    const r = parseJson(name, JSON.stringify(value), schema);
    expect(r.state === 'ok', name, describe(r));
  }
  const noDisease: Record<string, unknown> = { ...ex.farmWeeksYear };
  delete noDisease.disease;
  expect(parseJson('', JSON.stringify(noDisease), FarmWeeksYearSchema).state === 'ok', 'a year file without disease flags');

  // ---- 2 ----
  for (const scenario of ['pre', 'post'] as const) {
    heading(`2. Mock files, ${scenario === 'pre' ? 'before' : 'after'} the freeze (${MOCK}/${scenario})`);
    const files = filesIn(io, `${MOCK}/${scenario}`);
    for (const k of DATA_KEYS) {
      const s = files.data[k];
      if ((k === 'drivers' || k === 'combined' || k === 'farmerActions') && scenario === 'pre') {
        expect(s.state === 'missing', `${DATA_FILES[k].path} is absent before the freeze`, s.state);
        continue;
      }
      expect(s.state === 'ok', `${DATA_FILES[k].path} passes`, describe(s));
    }

    const { nowcast: nc, price: pr, channels: ch } = files.data;
    if (nc.state === 'ok') {
      const shape = [
        nc.data.f1 !== null,
        nc.data.latest !== null,
        nc.data.scores.holdout !== null,
        nc.data.backtest.some((r) => r.window === 'holdout'),
      ];
      expect(shape.every((x) => x === (scenario === 'post')), `nowcast.json has the ${scenario}-freeze shape`, String(shape));
    }
    if (pr.state === 'ok') {
      const shape = [
        pr.data.f2 !== null,
        pr.data.backtest_h4 !== null,
        pr.data.scorecard.some((r) => r.window === 'holdout'),
        pr.data.cw.some((r) => r.window === 'holdout'),
      ];
      expect(shape.every((x) => x === (scenario === 'post')), `price.json has the ${scenario}-freeze shape`, String(shape));
    }
    if (ch.state === 'ok') {
      expect((ch.data.panel != null) === (scenario === 'post'), `channels.json ${scenario === 'post' ? 'has' : 'lacks'} panel`);
    }

    const idx = files.data.farmWeeksIndex;
    const farms = files.data.farms;
    if (idx.state === 'ok' && farms.state === 'ok') {
      const known = new Set(farms.data.map((f) => f.id));
      for (const year of idx.data.years) {
        const y = fromDisk(io, `${MOCK}/${scenario}/farm_weeks/${year}.json`, FarmWeeksYearSchema);
        expect(y.state === 'ok', `farm_weeks/${year}.json passes`, describe(y));
        if (y.state === 'ok') {
          expect(y.data.ids.every((id) => known.has(id)), `every id in ${year}.json is in farms.json`);
          expect((y.data.disease !== undefined) === (scenario === 'post'), `${year}.json ${scenario === 'post' ? 'has' : 'lacks'} disease flags`);
        }
      }
    }

    for (const c of CHART_NAMES) {
      const s = files.charts[c];
      if (s.state === 'missing') continue;
      if (s.state !== 'ok') {
        expect(false, `charts/${c}.vl.json passes`, describe(s));
        continue;
      }
      try {
        const { svg, warnings, errors } = await drawChart(s.data);
        expect(svg.startsWith('<svg') && errors.length === 0, `charts/${c}.vl.json draws`, errors.join('; '));
        for (const w of warnings) console.log(`      note: ${w}`);
      } catch (e) {
        expect(false, `charts/${c}.vl.json draws`, e instanceof Error ? e.message : String(e));
      }
    }
  }

  // ---- 3 ----
  heading('3. The loader gives the right state for each kind of answer');
  const realFetch = globalThis.fetch;
  const answer = (body: string, status = 200, type = 'application/json') =>
    (async () => new Response(body, { status, headers: { 'content-type': type } })) as typeof fetch;
  const cases: [string, typeof fetch, Status<unknown>['state']][] = [
    ['404 → coming later', answer('Not found', 404, 'text/plain'), 'missing'],
    ['the site\'s own index.html instead of the file → coming later', answer('<!doctype html><html></html>', 200, 'text/html'), 'missing'],
    ['HTML sent as JSON → coming later', answer('<!doctype html>', 200, 'application/octet-stream'), 'missing'],
    ['NaN in the file → doesn\'t match', answer('[{"id": NaN}]'), 'invalid'],
    ['area 99 → doesn\'t match', answer(JSON.stringify([{ ...ex.farms[0], area: 99 }])), 'invalid'],
    ['a contract example → loaded', answer(JSON.stringify(ex.farms)), 'ok'],
    ['server error 500 → couldn\'t load', answer('oops', 500, 'text/plain'), 'error'],
    [
      'network failure → couldn\'t load',
      (async () => {
        throw new TypeError('Failed to fetch');
      }) as typeof fetch,
      'error',
    ],
  ];
  try {
    for (const [name, fake, want] of cases) {
      globalThis.fetch = fake;
      const r = await loadJson('data/farms.json', FarmsSchema);
      expect(r.state === want, name, `got ${r.state}`);
      if (name.startsWith('area 99') && r.state === 'invalid') {
        expect(r.problems.some((p) => p.startsWith('0.area')), 'the problem names the field', r.problems.join('; '));
      }
    }
  } finally {
    globalThis.fetch = realFetch;
  }

  // ---- 4 + 5 ----
  heading('4. The page renders in every scenario');
  const pre = filesIn(io, `${MOCK}/pre`);
  const post = filesIn(io, `${MOCK}/post`);
  const none = filesIn(io, `${MOCK}/none`);
  const brokenNowcast =
    post.data.nowcast.state === 'ok'
      ? parseJson(
          'nowcast.json',
          JSON.stringify({ ...post.data.nowcast.data, f1: { ...post.data.nowcast.data.f1, pass: 'yes' } }),
          NowcastSchema,
        )
      : post.data.nowcast;
  const broken: AllFiles = { ...post, data: { ...post.data, nowcast: brokenNowcast } };

  const scenarios: [string, AllFiles, string[]][] = [
    [
      'before the freeze',
      pre,
      ['Mock data: made-up numbers, not findings', "This test hasn't been scored yet.", 'Coming soon', 'Correlation with the salmon price', 'What happens to the harvest'],
    ],
    [
      'after the freeze',
      post,
      [
        'Pass',
        'Fail',
        'No pass mark',
        'less error than our baseline model',
        'How accurate it was',
        'Our first model, and the test it missed',
        'September 2026 by production area',
        'Lice and treatments',
        'How much worse the forecast gets without each factor',
        'Does the effect clear zero?',
        'Our forecast against the published harvest',
        'Forecast for October 2026',
        'Salmon harvested in each production area',
      ],
    ],
    ['with no files at all', none, ['Coming soon']],
    ['with a broken nowcast.json', broken, ['Not available right now', 'Fail']],
  ];
  // Words from the build that must never reach a visitor.
  const buildWords = /04:00|freeze|final model|final run|waiting for|arrives |from data\b|from production|from price|development window|back end|\.json/i;
  for (const [name, files, wants] of scenarios) {
    try {
      const text = textOf(
        renderToString(<SitePage files={files} source={{ kind: 'mock', scenario: 'pre' }} generation={0} onCheckAgain={() => {}} />),
      );
      const missing = wants.filter((w) => !text.includes(w));
      expect(!missing.length, `renders ${name}`, `missing text: ${missing.join(' | ')}`);
      const leaked = text.match(buildWords);
      expect(!leaked, `shows visitors no build notes ${name}`, leaked ? `found "${leaked[0]}" in: ${text.slice(Math.max(0, leaked.index! - 60), leaked.index! + 60)}` : '');
    } catch (e) {
      expect(false, `renders ${name}`, e instanceof Error ? e.stack : String(e));
    }
  }

  try {
    const text = textOf(renderToString(<App />));
    expect(text.includes('Loading'), 'the whole app renders its loading state');
  } catch (e) {
    expect(false, 'the whole app renders', e instanceof Error ? e.stack : String(e));
  }

  for (const scenario of ['pre', 'post'] as const) {
    const year = fromDisk(io, `${MOCK}/${scenario}/farm_weeks/2026.json`, FarmWeeksYearSchema);
    const farms = fromDisk(io, `${MOCK}/${scenario}/farms.json`, FarmsSchema);
    if (year.state !== 'ok' || farms.state !== 'ok') {
      expect(false, `finding 1 renders (${scenario})`, 'mock files missing');
      continue;
    }
    try {
      const text = textOf(
        renderToString(
          <FarmExplorer farms={farms.data} years={[2025, 2026]} year={2026} onYear={() => {}} data={year.data} source={{ kind: 'mock', scenario }} />,
        ),
      );
      const wants = [
        'Week 44',
        '26 Oct to 1 Nov 2026',
        'Colour the farms by',
        'Whole coast',
        'Mobile lice per fish',
        'Find a farm',
        'This week by area',
        'Sea temperature, by area',
        'South to north',
        'Farms reporting lice',
        scenario === 'pre' ? 'No disease flags in the data' : 'Farms flagged ISA or PD',
        'Averaged over the farms within about 10 km.',
        'Zoomed in:',
        'North',
        'Jul',
      ];
      const missing = wants.filter((w) => !text.includes(w));
      expect(!missing.length, `finding 1 renders the map's controls and a week (${scenario})`, `missing text: ${missing.join(' | ')}`);
    } catch (e) {
      expect(false, `finding 1 renders (${scenario})`, e instanceof Error ? e.stack : String(e));
    }
  }

  // ---- 5 ----
  heading('5. The farm map');
  const base = fromDisk(io, 'public/map/norway.json', BasemapSchema);
  expect(base.state === 'ok', 'public/map/norway.json passes, with the same projection and view as the code', describe(base));
  if (base.state === 'ok') {
    const kb = Math.round((io.read('public/map/norway.json') ?? '').length / 1024);
    expect(kb < 260, `the coastline file stays small (${kb} KB)`);
    expect(base.data.countries.includes('Norway') && base.data.countries.includes('Sweden'), 'it has Norway and its neighbours');
  }
  const inView = ([x, y]: [number, number]) => x > VIEW.x && x < VIEW.x + VIEW.w && y > VIEW.y && y < VIEW.y + VIEW.h;
  const bergen = project(5.3221, 60.3913);
  const trondheim = project(10.3951, 63.4305);
  const tromso = project(18.956, 69.6496);
  const northCape = project(25.7836, 71.1685);
  const lindesnes = project(7.0475, 57.9826);
  expect([bergen, trondheim, tromso, northCape, lindesnes].every(inView), 'Lindesnes, Bergen, Trondheim, Tromsø and the North Cape are in view');
  expect(bergen[0] < trondheim[0] && trondheim[0] < tromso[0] && tromso[1] < trondheim[1] && trondheim[1] < bergen[1], 'north is up and east is right');
  expect(Math.abs(Math.hypot(bergen[0] - trondheim[0], bergen[1] - trondheim[1]) - 433) < 15, 'Bergen to Trondheim is about 433 km on the map');

  const weekCases: [string, string][] = [
    ['2026-W44', '26 Oct to 1 Nov 2026'],
    ['2025-W41', '6 to 12 Oct 2025'],
    ['2026-W01', '29 Dec 2025 to 4 Jan 2026'],
    ['2020-W53', '28 Dec 2020 to 3 Jan 2021'],
  ];
  const badWeeks = weekCases.filter(([w, want]) => weekDates(w) !== want).map(([w]) => `${w} → ${weekDates(w)}`);
  expect(!badWeeks.length, 'ISO weeks turn into the right dates', badWeeks.join('; '));
  const weeks44 = Array.from({ length: 44 }, (_, i) => `2026-W${String(i + 1).padStart(2, '0')}`);
  expect(indexOfWeek(weeks44, 44) === 43 && indexOfWeek(weeks44, 53) === 43 && indexOfWeek(weeks44, 1) === 0, 'a week missing from a year falls back to the nearest one before it');

  const nameCases: [string, string][] = [
    ['REVØY', 'Revøy'],
    ['FINNKJERKA S', 'Finnkjerka S'],
    ['HÅGARDSNESET II', 'Hågardsneset II'],
    ['Aukan', 'Aukan'],
    ['SKÅR-HOLMEN 2', 'Skår-Holmen 2'],
  ];
  const badNames = nameCases.filter(([n, want]) => displayName(n) !== want).map(([n]) => `${n} → ${displayName(n)}`);
  expect(!badNames.length, 'capitalised farm names read as names', badNames.join('; '));
  expect(searchKey('Revøy') === 'revoy' && searchKey('ÆRØY') === 'aeroy' && searchKey('Hågardsneset') === 'hagardsneset', 'search ignores ø, æ and å');

  const liceBins = [0, 0.249, 0.25, 0.5, 0.75, 0.999, 1, 63].map((v) => binIndex(v, LICE_BREAKS));
  expect(liceBins.join() === '0,0,1,2,3,3,4,4', 'lice values land in the right colour bins', liceBins.join());
  const tempBins = [-0.2, 3.9, 4, 9, 9.99, 14, 21].map((v) => binIndex(v, TEMP_BREAKS));
  expect(tempBins.join() === '0,0,1,3,3,6,6' && TEMP_COLORS.length === TEMP_BREAKS.length + 1, 'temperatures land in the right bins, grey in the middle', tempBins.join());
  const blank = { mobile: null, temp: null, treated: null, disease: null };
  expect(
    markFor('lice', blank).shape === 'empty' &&
      markFor('treated', { ...blank, treated: 1 }).ring &&
      markFor('disease', { ...blank, disease: 1 }).shape === 'diamond' &&
      markFor('lice', { ...blank, mobile: 0.3, treated: 1 }).ring,
    'treated farms get a ring and flagged farms a diamond, not just a colour',
  );

  const badRamps = LAYERS.filter(
    (l) =>
      l.ramp.colors.length !== l.ramp.breaks.length + 1 ||
      l.ramp.labels.length !== l.ramp.colors.length ||
      (l.ramp.ticks !== undefined && l.ramp.ticks.length !== l.ramp.breaks.length),
  ).map((l) => l.key);
  expect(!badRamps.length, 'every layer has a heat ramp with one colour and label per bin', badRamps.join());
  const shareBins = [
    ...[0, 0.049, 0.05, 0.2, 0.349, 0.35, 1].map((v) => binIndex(v, TREATED_SHARE_BREAKS)),
    ...[0, 0.019, 0.02, 0.15, 0.3, 1].map((v) => binIndex(v, FLAGGED_SHARE_BREAKS)),
  ];
  expect(shareBins.join() === '0,0,1,3,3,4,4,0,0,1,3,4,4', 'shares of farms treated and flagged land in the right bins', shareBins.join());
  expect(
    heatValue('lice', { ...blank, mobile: 0.4 }) === 0.4 &&
      heatValue('treated', { ...blank, treated: 1 }) === 1 &&
      heatValue('disease', { ...blank, disease: 0 }) === 0 &&
      heatValue('temp', blank) === null,
    'the heat averages lice and temperature as they are, and treated and flagged as 1 or 0',
  );

  // Two weeks, three farms: two in area 1, one in area 13. No disease flags.
  const tiny = FarmWeeksYearSchema.parse({
    year: 2025,
    weeks: ['2025-W01', '2025-W02'],
    ids: [1, 2, 3],
    mobile: [
      [0.2, 0.4, null],
      [null, null, 1],
    ],
    treated: [
      [1, 0, null],
      [0, 0, 1],
    ],
    temp: [
      [6, 7, 3],
      [6.5, null, 2],
    ],
  });
  const areaOf = (id: number) => ({ 1: 1, 2: 1, 3: 13 })[id];
  const strip = areaWeeks(tiny, areaOf);
  const a1 = strip.find((r) => r.area === 1)!;
  const a13 = strip.find((r) => r.area === 13)!;
  const close = (a: number | null | undefined, b: number) => a != null && Math.abs(a - b) < 1e-9;
  expect(
    strip.map((r) => r.area).join() === AREAS_NORTH_FIRST.join() && AREAS_NORTH_FIRST[0] === 13 && AREAS_NORTH_FIRST.length === 13,
    'the year strip has all 13 areas, north at the top like the map',
  );
  expect(
    close(a1.mean.lice[0], 0.3) &&
      a1.count.lice[0] === 2 &&
      a1.mean.lice[1] === null &&
      a1.count.lice[1] === 0 &&
      close(a13.mean.lice[1], 1) &&
      close(a1.mean.treated[0], 0.5) &&
      close(a1.mean.temp[1], 6.5) &&
      a1.mean.disease.every((v) => v === null) &&
      strip.find((r) => r.area === 5)!.mean.lice.every((v) => v === null),
    'the year strip averages only the farms that reported, area by area and week by week',
  );

  // ---- 6 ----
  heading('6. The charts the site draws');
  const siteCharts: [string, ChartSpec | null][] =
    post.data.combined.state === 'ok' && post.data.price.state === 'ok' && post.data.areaMonth.state === 'ok'
      ? [
          ['forecast against published harvest', forecastSpec(post.data.combined.data)],
          ['price error by horizon', scorecardSpec(post.data.price.data)],
          ['price error by year', priceByYearSpec(post.data.price.data)],
          ['harvest by area and month', areaHeatSpec(post.data.areaMonth.data)],
        ]
      : [['the mock files', null]];
  for (const [name, spec] of siteCharts) {
    try {
      if (!spec) throw new Error('missing');
      const view = new vega.View(vega.parse(compile(spec as never).spec), { renderer: 'none' });
      const svg = await view.toSVG();
      view.finalize();
      expect(svg.startsWith('<svg'), `draws: ${name}`);
    } catch (e) {
      expect(false, `draws: ${name}`, e instanceof Error ? e.message : String(e));
    }
  }
  const kcw = (kg: number | null) => ({ kg, count: 1, avg_kg: 1 });
  const row = (area: number, month: string, pred: number | null) => ({ area, month, window: 'dev' as const, actual: kcw(10), pred: kcw(pred) });
  const totals = monthlyTotals({
    windows: { dev: ['2021-01', '2021-02'], holdout: ['2021-03', '2021-03'] },
    scores: { dev: { log_kg: null, log_count: null, log_avg_kg: null }, holdout: { log_kg: null, log_count: null, log_avg_kg: null } },
    backtest: [row(2, '2021-02', 12), row(3, '2021-02', 8), row(2, '2021-01', 5), row(3, '2021-01', null)],
  });
  expect(
    totals.length === 1 && totals[0]!.month === '2021-02' && totals[0]!.forecast === 20 && totals[0]!.published === 20,
    'monthly totals add up the areas and skip a month that is missing one',
  );
  expect(Math.abs(logToPct(0.07917)! - 8.24) < 0.01 && logToPct(null) === null, 'differences in logs turn into percentages');

  console.log(failures ? `\n${failures} check(s) failed.` : '\nAll checks passed.');
  return failures ? 1 : 0;
}
