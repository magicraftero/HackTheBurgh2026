// Checks the front end without a browser. Run with: npm run check
//
// 1. The contract's own examples (00-shared.md) pass the schemas.
// 2. The mocks pass, with the right before- and after-freeze shapes.
// 3. The loader turns every kind of server answer into the right state.
// 4. Every mock chart compiles and draws with Vega.
// 5. The page renders in every scenario, including a broken file.

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
import { FarmWeekSummary } from '../src/page/FarmWeeks';
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
      if (k === 'drivers' && scenario === 'pre') {
        expect(s.state === 'missing', 'drivers.json is absent before the freeze', s.state);
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
      [
        'Mock data: made-up numbers, not findings',
        'Holdout results land at the 04:00 analysis freeze.',
        'Holdout scores arrive at the 04:00 freeze.',
        'F1 is scored once, at the 04:00 freeze.',
        'The worked example arrives at the 04:00 freeze.',
        'Waiting for drivers.json from Production.',
        'M1 and M2 are scored at the 04:00 freeze.',
        'F2 is scored once, at the 04:00 freeze.',
        'Waiting for charts/price_backtest.vl.json from Price.',
        'Only if the back end has time.',
        '10 of 17 files in.', // 7 data files + 3 charts
      ],
    ],
    [
      'after the freeze',
      post,
      [
        'The holdout results are in.',
        'Pass',
        'Fail',
        'No pass mark',
        'lower error than baseline B1',
        'September 2026 by production area',
        'Lice and treatments',
        '16 of 17 files in.', // price_fan is optional and absent
      ],
    ],
    [
      'with no files at all',
      none,
      ['Waiting for farms.json from Data.', 'Waiting for trap.json from Production.', 'Waiting for price.json from Price.', '0 of 17 files in.'],
    ],
    ['with a broken nowcast.json', broken, ["nowcast.json is there but doesn't match the agreed format yet", 'f1.pass', 'Fail']],
  ];
  for (const [name, files, wants] of scenarios) {
    try {
      const text = textOf(
        renderToString(<SitePage files={files} source={{ kind: 'mock', scenario: 'pre' }} generation={0} onCheckAgain={() => {}} />),
      );
      const missing = wants.filter((w) => !text.includes(w));
      expect(!missing.length, `renders ${name}`, `missing text: ${missing.join(' | ')}`);
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
    const text = textOf(renderToString(<FarmWeekSummary data={year.data} farms={farms.data} />));
    const wants = ['2026-W44', 'Farms reporting lice', scenario === 'pre' ? 'No disease flags in the data' : 'Farms flagged ISA or PD'];
    const missing = wants.filter((w) => !text.includes(w));
    expect(!missing.length, `finding 1 renders a week (${scenario})`, `missing text: ${missing.join(' | ')}`);
  }

  console.log(failures ? `\n${failures} check(s) failed.` : '\nAll checks passed.');
  return failures ? 1 : 0;
}
