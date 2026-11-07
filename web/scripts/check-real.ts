// Checks the real findings files that have landed in public/data and
// public/charts against the contract (00-shared.md), and that each chart
// draws. Problems are for the file's owner to fix; the site never adapts
// silently. Run with: npm run check:real
import * as vega from 'vega';
import { compile } from 'vega-lite';
import type { z } from 'zod';
import { CHART_NAMES, CHARTS, DATA_FILES, DATA_KEYS, chartPath, farmWeeksYearPath } from '../src/data/files';
import { parseJson } from '../src/data/load';
import { ChartSpecSchema, FarmWeeksYearSchema, type ChartSpec, type Farms, type FarmWeeksIndex, type Price } from '../src/data/schemas';
import type { IO } from './io';

async function draw(spec: ChartSpec): Promise<{ svg: string; warnings: string[] }> {
  const warnings: string[] = [];
  const { warn } = console;
  console.warn = (...a: unknown[]) => void warnings.push(a.map(String).join(' '));
  try {
    const view = new vega.View(vega.parse(compile(spec as never).spec), { renderer: 'none' });
    const svg = await view.toSVG();
    view.finalize();
    return { svg, warnings: [...new Set(warnings)] };
  } finally {
    console.warn = warn;
  }
}

export default async function main(io: IO): Promise<number> {
  let problems = 0;
  const say = (symbol: string, text: string) => console.log(`  ${symbol} ${text}`);
  const detail = (text: string) => console.log(`      ${text}`);
  const loaded: Partial<Record<string, unknown>> = {};

  console.log('\nData files (public/data)');
  for (const key of DATA_KEYS) {
    const def = DATA_FILES[key];
    const text = io.read(`public/${def.path}`);
    if (text === null) {
      say('○', `${def.path}: not there yet (due ${def.due}, ${def.owner})`);
      continue;
    }
    const r = parseJson(def.path, text, def.schema as z.ZodType<unknown>);
    if (r.state === 'ok') {
      loaded[key] = r.data;
      say('✓', `${def.path}: matches the contract (${Math.round(text.length / 1024)} KB)`);
    } else {
      problems += 1;
      say('✕', `${def.path}: doesn't match the contract. Tell ${def.owner}:`);
      if (r.state === 'invalid') r.problems.forEach(detail);
    }
  }

  const farms = loaded.farms as Farms | undefined;
  const index = loaded.farmWeeksIndex as FarmWeeksIndex | undefined;
  if (farms) {
    const areas = new Set(farms.map((f) => f.area));
    detail(`farms.json: ${farms.length} farms in ${areas.size} areas; ${farms.filter((f) => f.lat === null || f.lon === null).length} without a position`);
  }

  if (index) {
    console.log('\nFarm year files (public/data/farm_weeks)');
    const known = farms ? new Set(farms.map((f) => f.id)) : null;
    for (const year of [...index.years].sort((a, b) => a - b)) {
      const path = farmWeeksYearPath(year);
      const text = io.read(`public/${path}`);
      if (text === null) {
        problems += 1;
        say('✕', `${path}: listed in index.json but missing. Tell Data.`);
        continue;
      }
      const r = parseJson(path, text, FarmWeeksYearSchema);
      if (r.state !== 'ok') {
        problems += 1;
        say('✕', `${path}: doesn't match the contract. Tell Data:`);
        if (r.state === 'invalid') r.problems.forEach(detail);
        continue;
      }
      const unknown = known ? r.data.ids.filter((id) => !known.has(id)).length : 0;
      const notes = [
        `${r.data.weeks.length} weeks`,
        `${r.data.ids.length} farms`,
        `${Math.round(text.length / 1024)} KB`,
        r.data.disease ? 'with disease flags' : 'no disease flags',
      ];
      if (unknown) {
        problems += 1;
        notes.push(`${unknown} ids not in farms.json (tell Data)`);
      }
      say(unknown ? '✕' : '✓', `${path}: ${notes.join(', ')}`);
    }
  }

  const price = loaded.price as Price | undefined;
  if (price) {
    const windows = [...new Set(price.scorecard.map((r) => r.window))].join(' and ') || 'none';
    console.log('\nprice.json shape');
    detail(`history ${price.history[0]?.week ?? '?'} to ${price.history[price.history.length - 1]?.week ?? '?'} (${price.history.length} weeks)`);
    detail(`scorecard windows: ${windows}; f2 ${price.f2 ? 'filled in' : 'null (before the freeze)'}; backtest_h4 ${price.backtest_h4 ? `${price.backtest_h4.length} weeks` : 'null (before the freeze)'}`);
    detail(`current ${price.current == null ? 'null' : 'filled in (format not agreed yet: ask Price)'}`);
    if (price.notes.length) detail(`notes: ${price.notes.join(' | ')}`);
  }

  console.log('\nCharts (public/charts)');
  for (const name of CHART_NAMES) {
    const path = chartPath(name);
    const text = io.read(`public/${path}`);
    if (text === null) {
      say('○', `${path}: not there yet (due ${CHARTS[name].due}, ${CHARTS[name].owner})`);
      continue;
    }
    const r = parseJson(path, text, ChartSpecSchema);
    if (r.state !== 'ok') {
      problems += 1;
      say('✕', `${path}: not a valid chart spec. Tell ${CHARTS[name].owner}.`);
      continue;
    }
    try {
      const { svg, warnings } = await draw(r.data);
      say('✓', `${path}: draws (${Math.round(svg.length / 1024)} KB of SVG)`);
      warnings.forEach((w) => detail(`note: ${w}`));
    } catch (e) {
      problems += 1;
      say('✕', `${path}: fails to draw (${e instanceof Error ? e.message : String(e)}). Tell ${CHARTS[name].owner}.`);
    }
  }

  console.log(problems ? `\n${problems} problem(s) to report.` : '\nEverything that has landed matches the contract.');
  return problems ? 1 : 0;
}
