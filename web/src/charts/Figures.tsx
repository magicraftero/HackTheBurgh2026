// The findings as pictures, drawn from the published data. Simple comparisons
// are plain HTML (they scale with the page and stay crisp); time series use
// Vega-Lite (./specs.ts). Each has a table under "Show the numbers".

import { Fragment, useMemo, type CSSProperties, type ReactNode } from 'react';
import { DASH, fmtPct, fmtR, fmtTonnes } from '../components/format';
import { VegaChart } from '../components/VegaChart';
import type { AreaMonth, ChartSpec, Channels, Combined, FarmerActions, Price, Trap } from '../data/schemas';
import { areaHeatSpec, forecastSpec, priceByYearSpec, priceForecastSpec, priceWindow, scorecardSpec } from './specs';

function Figure({ title, legend, note, children }: { title: string; legend?: ReactNode; note?: ReactNode; children: ReactNode }) {
  return (
    <div className="chart-card">
      <figure className="figure" aria-label={title}>
        <figcaption className="figure-head">
          <h3>{title}</h3>
          {legend}
        </figcaption>
        {children}
        {note ? <p className="figure-note">{note}</p> : null}
      </figure>
    </div>
  );
}

function VegaFigure({ title, note, spec }: { title: string; note?: ReactNode; spec: Parameters<typeof VegaChart>[0]['spec'] }) {
  return (
    <Figure title={title} note={note}>
      <VegaChart spec={spec} label={title} />
    </Figure>
  );
}

/** A signed percentage that never says "−0.0%". */
export const rise = (v: number | null) => (v === null ? DASH : Math.abs(v) < 0.05 ? '0.0%' : fmtPct(v));

const lowerFirst = (s: string) => (/^[A-Z][a-z]/.test(s) ? s[0]!.toLowerCase() + s.slice(1) : s);

// ---- correlation with price, before and after ----

export function TrapFigure({ trap }: { trap: Trap }) {
  const rows = trap.drivers
    .flatMap((d) => (d.raw_r === null || d.anom_r === null ? [] : [{ label: d.label, raw: d.raw_r, clean: d.anom_r }]))
    .sort((a, b) => Math.abs(b.raw) - Math.abs(a.raw));
  const top = rows[0];
  if (!top) return null;
  const all = rows.flatMap((r) => [r.raw, r.clean]);
  const lo = Math.min(-0.8, Math.floor(Math.min(...all) * 5) / 5);
  const hi = Math.max(0, Math.ceil(Math.max(...all) * 5) / 5);
  const x = (v: number) => ((v - lo) / (hi - lo)) * 100;
  const ticks: number[] = [];
  for (let t = lo; t <= hi + 1e-9; t += 0.2) ticks.push(Math.round(t * 10) / 10);
  const grew = rows.find((r) => Math.abs(r.clean) > Math.abs(r.raw));
  return (
    <Figure
      title="Correlation with the salmon price, before and after removing the seasons"
      legend={
        <p className="fig-legend" aria-hidden="true">
          <span>
            <i className="db-dot is-raw" /> Raw
          </span>
          <span>
            <i className="db-dot is-clean" /> Season and trend removed
          </span>
        </p>
      }
      note={
        <>
          The strongest raw link, {lowerFirst(top.label)} at {fmtR(top.raw)}, falls to {fmtR(top.clean)} once season and trend are
          gone.{grew ? ` ${grew.label} is the exception: its link gets stronger.` : ''}
        </>
      }
    >
      <div className="db" aria-hidden="true">
        {rows.map((r) => (
          <div className="db-row" key={r.label}>
            <span className="db-label">{r.label}</span>
            <span className="db-track">
              {ticks.map((t) => (
                <i key={t} className="db-tick" style={{ left: `${x(t)}%` }} />
              ))}
              <i className="db-link" style={{ left: `${Math.min(x(r.raw), x(r.clean))}%`, width: `${Math.abs(x(r.raw) - x(r.clean))}%` }} />
              <i className="db-dot is-raw" style={{ left: `${x(r.raw)}%` }} />
              <i className="db-dot is-clean" style={{ left: `${x(r.clean)}%` }} />
            </span>
            <span className="db-values">
              {fmtR(r.raw)} → {fmtR(r.clean)}
            </span>
          </div>
        ))}
        <div className="db-row db-axis">
          <span />
          <span className="db-track">
            {ticks.map((t) => (
              <em key={t} style={{ left: `${x(t)}%` }}>
                {t === 0 ? '0' : `${t < 0 ? '−' : ''}${Math.abs(t).toFixed(1)}`}
              </em>
            ))}
          </span>
          <span />
        </div>
      </div>
    </Figure>
  );
}

// ---- fish count and weight after low, middle and high months ----

export const FACTOR_NAMES: Record<string, string> = { lice: 'Lice', mortality: 'Deaths', temp: 'Sea temperature', feed: 'Feed' };
const FACTOR_ORDER = ['lice', 'mortality', 'temp', 'feed'];
export const THIRDS: Record<number, string> = { 1: 'Low', 2: 'Middle', 3: 'High' };

/** A difference in logs from normal, as a percentage: 0.079 is +8.2%. */
export const logToPct = (v: number | null) => (v === null ? null : (Math.exp(v) - 1) * 100);

type SplitKind = 'count' | 'weight';
type SplitRange = { lo: number; hi: number };

/** The range a column has to show. It always includes zero, which is "normal". */
export function splitRange(values: (number | null)[]): SplitRange {
  const known = values.filter((v): v is number => v !== null);
  return { lo: Math.min(0, ...known), hi: Math.max(0, ...known) };
}

const rangeSpan = ({ lo, hi }: SplitRange) => Math.max(hi - lo, 0.1);
const rangePct = (range: SplitRange, v: number) => ((v - range.lo) / rangeSpan(range)) * 100;

function SplitAxis({ kind, title, less, more, range }: { kind: SplitKind; title: string; less: string; more: string; range: SplitRange }) {
  return (
    <div className={`split-axis is-${kind}`} style={{ '--zero': `${rangePct(range, 0)}%` } as CSSProperties}>
      <strong>{title}</strong>
      <span className="split-less">← {less}</span>
      <span className="split-more">{more} →</span>
    </div>
  );
}

function SplitBar({ kind, value, range, middle, label }: { kind: SplitKind; value: number | null; range: SplitRange; middle: boolean; label: string }) {
  const zero = rangePct(range, 0);
  const tip = value === null ? zero : rangePct(range, value);
  // Anything that rounds to 0.0% keeps its number on the right, like a rise.
  const down = value !== null && value <= -0.05;
  return (
    <div className={`split-track is-${kind}${middle ? ' is-middle' : ''}`} style={{ '--zero': `${zero}%`, '--tip': `${tip}%` } as CSSProperties} title={label}>
      {value === null ? null : (
        <i className={`split-bar${value < 0 ? ' is-down' : ''}`} style={{ left: `${Math.min(zero, tip)}%`, width: `${Math.abs(tip - zero)}%` }} />
      )}
      <span className={`split-value${down ? ' is-down' : ''}`}>{rise(value)}</span>
    </div>
  );
}

export function SplitFigure({ bins }: { bins: Channels['bins'] }) {
  const rows = bins.map((b) => ({ ...b, count: logToPct(b.count_anom), weight: logToPct(b.weight_anom) }));
  const count = splitRange(rows.map((r) => r.count));
  const weight = splitRange(rows.map((r) => r.weight));
  const drivers = [...new Set(rows.map((r) => r.driver))].sort((a, b) => FACTOR_ORDER.indexOf(a) - FACTOR_ORDER.indexOf(b));
  // Each column is as wide as the range it shows, so one percentage point is
  // the same length in both.
  const widths = { '--count-fr': `${rangeSpan(count)}fr`, '--weight-fr': `${rangeSpan(weight)}fr` } as CSSProperties;
  return (
    <Figure
      title="What happens to the harvest after a low, middle or high month"
      note="Each factor's months are split into thirds. Bars show how far the harvest was from normal for the time of year. Both columns use the same scale."
    >
      <div className="split-chart" style={widths} aria-hidden="true">
        <div className="split-head">
          <SplitAxis kind="count" title="Fish harvested" less="Fewer" more="More" range={count} />
          <SplitAxis kind="weight" title="Average weight" less="Smaller" more="Bigger" range={weight} />
        </div>
        {drivers.map((driver) => {
          const part = rows.filter((r) => r.driver === driver).sort((a, b) => a.tercile - b.tercile);
          const name = FACTOR_NAMES[driver] ?? driver;
          return (
            <div className="split-block" key={driver}>
              <p className="split-factor">
                <strong>{name}</strong>
                <span>{part[0]?.window.replace('-', ' to ')} months later</span>
              </p>
              {part.map((r) => {
                const level = String(THIRDS[r.tercile] ?? r.tercile);
                const say = (what: string, v: number | null) => `${name}, ${level.toLowerCase()} months: ${what} ${rise(v)} against normal`;
                return (
                  <Fragment key={r.tercile}>
                    <span className="split-level">{level}</span>
                    <SplitBar kind="count" value={r.count} range={count} middle={r.tercile === 2} label={say('fish harvested', r.count)} />
                    <SplitBar kind="weight" value={r.weight} range={weight} middle={r.tercile === 2} label={say('average weight', r.weight)} />
                  </Fragment>
                );
              })}
            </div>
          );
        })}
      </div>
    </Figure>
  );
}

// ---- forecast against the published harvest ----

export function ForecastFigure({ c }: { c: Combined }) {
  const spec = useMemo(() => forecastSpec(c), [c]);
  return (
    <VegaFigure
      title="Our forecast against the published harvest, month by month"
      note="Total for the areas forecast. Area 1 and area 13 harvest too irregularly to forecast."
      spec={spec}
    />
  );
}

// ---- the price forecast against the actual price ----

export function PriceForecastFigure({ team, note }: { team: ChartSpec; note: ReactNode }) {
  const spec = useMemo(() => priceForecastSpec(team), [team]);
  return <VegaFigure title="Our price forecast against the actual price, week by week" note={note} spec={spec} />;
}

// ---- the price forecasts ----

export function ScorecardFigure({ p }: { p: Price }) {
  const spec = useMemo(() => scorecardSpec(p), [p]);
  const years = priceWindow(p) === 'holdout' ? 'The weeks the models never saw.' : 'The years the models were built on, 2021 to 2024.';
  return <VegaFigure title="Price forecast error at each horizon" note={`Below the line beats a random walk. ${years}`} spec={spec} />;
}

export function ByYearFigure({ p }: { p: Price }) {
  const spec = useMemo(() => priceByYearSpec(p), [p]);
  const years = p.by_year.map((y) => y.year);
  const span = years.length ? ` ${Math.min(...years)} to ${Math.max(...years)}, the years the models were built on.` : '';
  return <VegaFigure title="Does farm data help the four-week forecast?" note={`Lower is better.${priceWindow(p) === 'dev' ? span : ''}`} spec={spec} />;
}

// ---- Next forecast: the latest month, area by area ----

export function LiveForecast({ f }: { f: FarmerActions }) {
  const areas = f.areas.flatMap((a) => (a.forecast?.kg == null ? [] : [{ ...a, kg: a.forecast.kg }])).sort((a, b) => a.area - b.area);
  const max = Math.max(1, ...areas.map((a) => a.kg));
  return (
    <div className="chart-card">
      <div className="rank live-areas">
        <p className="rank-title">By production area, south to north</p>
        {areas.map((a) => (
          <div className="rank-row" key={a.area}>
            <span className="rank-label" title={a.name}>
              <b>{a.area}</b> {a.name}
            </span>
            <span className="rank-track">
              <i className="rank-bar" style={{ width: `${(a.kg / max) * 100}%` }} />
            </span>
            <span className="rank-value">{fmtTonnes(a.kg)}</span>
            <span className="live-change" title="Compared with the same month last year">
              {a.vs_last_year_pct === null ? DASH : fmtPct(a.vs_last_year_pct, 0)}
            </span>
          </div>
        ))}
        <p className="figure-note">Right-hand column: compared with the same month last year.</p>
      </div>
    </div>
  );
}

// ---- Appendix: every area, every month ----

export function AreaHeatFigure({ rows }: { rows: AreaMonth }) {
  const spec = useMemo(() => areaHeatSpec(rows), [rows]);
  return <VegaFigure title="Salmon harvested in each production area, every month" spec={spec} />;
}
