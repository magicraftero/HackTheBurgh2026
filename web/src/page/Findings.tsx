import type { ReactNode } from 'react';
import { LaterPill, PassPill, Pill, Reveal } from '../components/Bits';
import { Boundary } from '../components/Boundary';
import { DASH, fmt, fmtDate, fmtInt, fmtMonth, fmtP, fmtPct, fmtR, fmtTonnes } from '../components/format';
import { IconAlert, IconPlus } from '../components/Icons';
import { Later, StatusView } from '../components/States';
import { VegaChart } from '../components/VegaChart';
import { CHARTS, DATA_FILES, chartPath, type ChartName, type DataKey } from '../data/files';
import type { Status } from '../data/load';
import type { AreaMonth, Channels, Drivers, Nowcast, Price, Trap } from '../data/schemas';
import type { AllFiles, Source } from '../data/source';
import { FarmSection } from './FarmWeeks';

// The eight findings from docs/plans/frontend.md, in the plan's order.

const OUTCOMES: Record<string, string> = {
  log_kg: 'Volume (log kg)',
  log_count: 'Fish count (log)',
  log_avg_kg: 'Average weight (log kg)',
};
const MODELS: Record<string, string> = { b0: 'B0', b1: 'B1', drivers: 'Drivers', rw: 'Random walk' };
const outcomeLabel = (o: string) => OUTCOMES[o] ?? o;
const modelLabel = (m: string) => MODELS[m] ?? m;

const fileProps = (key: DataKey) => ({
  file: DATA_FILES[key].path.replace(/^data\//, ''),
  owner: DATA_FILES[key].owner,
  due: DATA_FILES[key].due,
});

export function Findings({ files, source }: { files: AllFiles; source: Source }) {
  const { data, charts } = files;
  const chart = (name: ChartName, label: string) => <ChartCard status={charts[name]} name={name} label={label} />;

  return (
    <>
      <Finding n={1} id="farms" band="cream" tag="Data" title="Every farm, every week." lede="Lice, treatments, disease and sea temperature, as each farm reported them. Pick a year, then slide through its weeks.">
        <FarmSection farms={data.farms} index={data.farmWeeksIndex} source={source} />
      </Finding>

      <Finding n={2} id="trap" band="paper" tag="Production" title="The seasonality trap." lede="Lice, temperature and price all swing with the seasons, so raw correlations look strong. Remove season and trend, and see what's left.">
        {chart('trap', 'Raw and anomaly correlations of each driver with price')}
        <StatusView status={data.trap} {...fileProps('trap')}>
          {(t) => (
            <Numbers>
              <TrapTable trap={t} />
            </Numbers>
          )}
        </StatusView>
      </Finding>

      <Finding n={3} id="split" band="cream" tag="Production" title="More fish, or bigger fish?" lede="Harvest is fish count × average weight. Fast growth gives more and bigger fish; harvests forced early by lice or disease give more but smaller ones. Only the split tells them apart.">
        {chart('channels_bins', 'Count and weight anomalies by tercile of each driver')}
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) => (
            <Numbers>
              <BinsTable bins={c.bins} />
            </Numbers>
          )}
        </StatusView>
      </Finding>

      <Finding n={4} id="nowcast" band="paper" tag="Production · F1" title="Called before it's published." lede="On the 10th of each month we nowcast the month just ended, area by area, using only data public by then. The Directorate publishes around the 20th. Here's how the Drivers model did against two baselines.">
        {chart('nowcast_backtest', 'Nowcast error by model, and national harvest against the nowcast')}
        <StatusView status={data.nowcast} {...fileProps('nowcast')}>
          {(nc) => <NowcastDetails nc={nc} />}
        </StatusView>
      </Finding>

      <Finding n={5} id="drivers" band="cream" tag="Production" title="What drives it." lede="Leave each group of drivers out and measure how much worse the nowcast gets. Exploratory: there's no pass mark.">
        {chart('drivers_importance', 'Rise in nowcast error without each driver group')}
        <StatusView status={data.drivers} {...fileProps('drivers')}>
          {(d) => (
            <Numbers>
              <DriversTable d={d} />
            </Numbers>
          )}
        </StatusView>
      </Finding>

      <Finding n={6} id="mechanisms" band="paper" tag="Production · M1, M2" title="How lice and warmth move the harvest." lede="M1, the lice signature: do lice bring harvests forward, with more but smaller fish? M2, growth: does warmer water grow heavier fish? Each with a 95% interval, pass or fail.">
        {chart('channels_panel', 'M1 and M2 coefficient sums with 95% intervals')}
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) =>
            c.panel ? (
              <Numbers>
                <PanelTable panel={c.panel} />
              </Numbers>
            ) : (
              <Later>
                <p>M1 and M2 are scored at the 04:00 freeze.</p>
                <p className="note">
                  Waiting for the <code>panel</code> part of channels.json from Production.
                </p>
              </Later>
            )
          }
        </StatusView>
      </Finding>

      <Finding n={7} id="price" band="cream" tag="Price · F2" title="The price, weeks ahead." lede="The weekly export price of fresh salmon, forecast 2 to 8 weeks ahead and scored against a random walk. F2 asks whether the farm drivers make the 4-week forecast better.">
        <div className="split-2">
          {chart('price_scorecard', 'Price forecast error relative to the random walk, by horizon')}
          {chart('price_by_year', 'c0 against c1 error by year')}
        </div>
        {chart('price_backtest', 'Actual price against the forecasts over the holdout, with a band')}
        <StatusView status={data.price} {...fileProps('price')}>
          {(p) => <PriceDetails p={p} />}
        </StatusView>
      </Finding>

      <Finding n={8} id="current" band="paper" tag="Optional" title="Right now." lede="Forecasts from the data available today. They can't be checked until after the event, so they never replace the backtest.">
        <CurrentForecasts nowcast={data.nowcast} price={data.price} />
        {charts.price_fan.state === 'ok' ? (
          <div className="chart-card">
            <p className="unverifiable">
              <IconAlert size={18} /> Unverifiable until after the event
            </p>
            <VegaChart spec={charts.price_fan.data} label="Current price forecast" />
          </div>
        ) : null}
      </Finding>

      <Finding id="area-month" band="cream" tag="Appendix" title="Harvest by area and month." lede="The monthly table behind the other findings.">
        <StatusView status={data.areaMonth} {...fileProps('areaMonth')}>
          {(rows) => <AreaMonthDetails rows={rows} />}
        </StatusView>
      </Finding>
    </>
  );
}

// ---- Building blocks ----

type FindingProps = {
  n?: number;
  id: string;
  band: 'paper' | 'cream';
  tag: string;
  title: string;
  lede: string;
  children: ReactNode;
};

function Finding({ n, id, band, tag, title, lede, children }: FindingProps) {
  return (
    <section className={`band band-${band} finding`} id={id} aria-labelledby={`${id}-title`}>
      <div className="container">
        <Reveal className="section-head">
          <div>
            <p className="eyebrow">
              {n ? (
                <span className="eyebrow-number" aria-hidden="true">
                  {n}
                </span>
              ) : null}
              <span>
                {n ? <span className="sr-only">Finding {n}: </span> : null}
                {tag}
              </span>
            </p>
            <h2 id={`${id}-title`}>{title}</h2>
            <p className="lede">{lede}</p>
          </div>
        </Reveal>
        <div className="finding-body">
          <Boundary what={title}>{children}</Boundary>
        </div>
      </div>
    </section>
  );
}

function ChartCard({ status, name, label }: { status: Status<Record<string, unknown>>; name: ChartName; label: string }) {
  return (
    <div className="chart-card">
      <StatusView status={status} file={chartPath(name)} owner={CHARTS[name].owner} due={CHARTS[name].due}>
        {(spec) => <VegaChart spec={spec} label={label} />}
      </StatusView>
    </div>
  );
}

function Numbers({ title = 'Show the numbers', children }: { title?: string; children: ReactNode }) {
  return (
    <details className="numbers">
      <summary>
        {title}
        <IconPlus size={20} />
      </summary>
      <div className="numbers-body">{children}</div>
    </details>
  );
}

function Table({ caption, head, children }: { caption: string; head: string[]; children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function MiniStats({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="mini-stats">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---- Finding 2 ----

function TrapTable({ trap }: { trap: Trap }) {
  return (
    <>
      <Table caption={`Correlation with log price, ${trap.from} to ${trap.to}`} head={['Driver', 'Raw', 'Season and trend removed']}>
        {trap.drivers.map((d) => (
          <tr key={d.driver}>
            <th scope="row">
              {d.label}
              {d.driver === trap.highlight ? ' (in the chart)' : ''}
            </th>
            <td>{fmtR(d.raw_r)}</td>
            <td>{fmtR(d.anom_r)}</td>
          </tr>
        ))}
      </Table>
      <p className="note">{fmtInt(trap.series.length)} weeks in the highlighted driver's series.</p>
    </>
  );
}

// ---- Finding 3 ----

function BinsTable({ bins }: { bins: Channels['bins'] }) {
  return (
    <Table caption="Anomalies by tercile of each driver" head={['Driver', 'Lags', 'Tercile', 'Count anomaly', 'Weight anomaly', 'Area-months']}>
      {bins.map((b) => (
        <tr key={`${b.driver}-${b.tercile}`}>
          <th scope="row">{b.driver}</th>
          <td>{b.window}</td>
          <td>{b.tercile}</td>
          <td>{fmt(b.count_anom, 3)}</td>
          <td>{fmt(b.weight_anom, 3)}</td>
          <td>{fmtInt(b.n)}</td>
        </tr>
      ))}
    </Table>
  );
}

// ---- Finding 4 ----

function NowcastDetails({ nc }: { nc: Nowcast }) {
  const devRows = nc.backtest.filter((r) => r.window === 'dev').length;
  return (
    <>
      <div className="split-2">
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>Test F1, on the holdout</h3>
            {nc.f1 ? <PassPill pass={nc.f1.pass} /> : <LaterPill>Scored at 04:00</LaterPill>}
          </div>
          {nc.f1 ? (
            <MiniStats
              items={[
                ['Error, baseline B1', fmt(nc.f1.mae_b1, 3)],
                ['Error, Drivers', fmt(nc.f1.mae_drivers, 3)],
                ['Improvement', fmtPct(nc.f1.improvement_pct)],
                ['Clark–West p', fmtP(nc.f1.cw_p)],
              ]}
            />
          ) : (
            <p className="note">F1 is scored once, at the 04:00 freeze. Development-window results never stand in for it.</p>
          )}
        </div>
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>Worked example</h3>
            {nc.latest ? <Pill tone="accent">{fmtMonth(nc.latest.month)}</Pill> : <LaterPill>Arrives 04:00</LaterPill>}
          </div>
          {nc.latest ? (
            <MiniStats
              items={[
                ['Nowcast, areas 1–13', fmtTonnes(nc.latest.national.pred_kg)],
                ['Published', fmtTonnes(nc.latest.national.actual_kg)],
                ['Error', fmtPct(nc.latest.national.error_pct)],
                ['Called on', fmtDate(nc.latest.made_on)],
              ]}
            />
          ) : (
            <p className="note">The worked example arrives at the 04:00 freeze.</p>
          )}
        </div>
      </div>
      <Numbers>
        <p>
          Development window {nc.windows.dev[0]} to {nc.windows.dev[1]}; holdout {nc.windows.holdout[0]} to{' '}
          {nc.windows.holdout[1]}. Backtest rows: {fmtInt(devRows)} development, {fmtInt(nc.backtest.length - devRows)} holdout.
          Actuals: {nc.scores.actuals}.
        </p>
        <ScoresTable caption="Mean absolute error, development window" scores={nc.scores.dev} models={nc.models} />
        {nc.scores.holdout ? (
          <ScoresTable caption="Mean absolute error, holdout" scores={nc.scores.holdout} models={nc.models} />
        ) : (
          <Later>
            <p>Holdout scores arrive at the 04:00 freeze.</p>
          </Later>
        )}
        {nc.latest ? (
          <Table caption={`${fmtMonth(nc.latest.month)} by production area`} head={['Area', 'Nowcast', 'Published', 'Error']}>
            {nc.latest.areas.map((a) => (
              <tr key={a.area}>
                <th scope="row">{a.area}</th>
                <td>{fmtTonnes(a.pred_kg)}</td>
                <td>{fmtTonnes(a.actual_kg)}</td>
                <td>{fmtPct(a.error_pct)}</td>
              </tr>
            ))}
          </Table>
        ) : null}
      </Numbers>
    </>
  );
}

type Scores = Record<string, Record<string, number | null>>;

function ScoresTable({ caption, scores, models }: { caption: string; scores: Scores; models: string[] }) {
  return (
    <Table caption={caption} head={['Outcome', ...models.map(modelLabel)]}>
      {Object.keys(scores).map((o) => (
        <tr key={o}>
          <th scope="row">{outcomeLabel(o)}</th>
          {models.map((m) => (
            <td key={m}>{fmt(scores[o]?.[m], 3)}</td>
          ))}
        </tr>
      ))}
    </Table>
  );
}

// ---- Finding 5 ----

function DriversTable({ d }: { d: Drivers }) {
  const sorted = [...d.groups].sort((a, b) => (b.increase_pct ?? -Infinity) - (a.increase_pct ?? -Infinity));
  const others = Object.keys(d.by_outcome);
  return (
    <>
      <p>
        {outcomeLabel(d.outcome)}, {d.window}. Error with every driver in: {fmt(d.full_mae, 3)}.
      </p>
      <Table caption="Rise in error when each group is left out" head={['Group', 'Error without it', 'Rise in error', ...others.map((o) => `Rise: ${outcomeLabel(o)}`)]}>
        {sorted.map((g) => (
          <tr key={g.group}>
            <th scope="row">{g.label}</th>
            <td>{fmt(g.mae_without, 3)}</td>
            <td>{fmtPct(g.increase_pct)}</td>
            {others.map((o) => (
              <td key={o}>{fmtPct(d.by_outcome[o]?.find((x) => x.group === g.group)?.increase_pct)}</td>
            ))}
          </tr>
        ))}
      </Table>
    </>
  );
}

// ---- Finding 6 ----

function PanelTable({ panel }: { panel: NonNullable<Channels['panel']> }) {
  return (
    <Table caption="Sums of lag coefficients, with 95% intervals" head={['Test', 'Outcome', 'Driver', 'Lags', 'Sum', '95% interval', 'Result']}>
      {panel.map((r, i) => (
        <tr key={`${r.test}-${r.outcome}-${r.driver}-${i}`}>
          <th scope="row">{r.test}</th>
          <td>{r.outcome}</td>
          <td>{r.driver}</td>
          <td>{r.lags}</td>
          <td>{fmt(r.coef_sum, 4)}</td>
          <td>
            {fmt(r.lo, 4)} to {fmt(r.hi, 4)}
          </td>
          <td>{r.pass === null ? 'No pass mark' : <PassPill pass={r.pass} />}</td>
        </tr>
      ))}
    </Table>
  );
}

// ---- Finding 7 ----

function PriceDetails({ p }: { p: Price }) {
  const primaryH = p.cw.find((c) => c.primary)?.h ?? null;
  const rows = primaryH === null ? [] : p.scorecard.filter((r) => r.h === primaryH);
  const last = p.history[p.history.length - 1];
  return (
    <>
      <div className="chart-card">
        <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3>Test F2, on the holdout</h3>
          {p.f2 ? <PassPill pass={p.f2.pass} /> : <LaterPill>Scored at 04:00</LaterPill>}
        </div>
        {p.f2 ? (
          <MiniStats
            items={[
              ['Error, c0', fmt(p.f2.mae_c0, 3)],
              ['Error, c1 (with drivers)', fmt(p.f2.mae_c1, 3)],
              ['Clark–West p', fmtP(p.f2.cw_p)],
              ['Latest price', last ? `${fmt(last.price_nok_kg)} NOK/kg` : DASH],
            ]}
          />
        ) : (
          <p className="note">F2 is scored once, at the 04:00 freeze. Development-window results never stand in for it.</p>
        )}
      </div>
      <Numbers>
        <p>
          Development window {p.windows.dev[0]} to {p.windows.dev[1]}; holdout {p.windows.holdout[0]} to{' '}
          {p.windows.holdout[1]}. Price history: {fmtInt(p.history.length)} weeks
          {last ? `, latest ${last.week} at ${fmt(last.price_nok_kg)} NOK/kg` : ''}.
        </p>
        {rows.length ? (
          <Table caption={`Scorecard, ${primaryH} weeks ahead`} head={['Window', 'Model', 'Error', 'vs random walk', 'Direction right']}>
            {rows.map((r) => (
              <tr key={`${r.window}-${r.model}`}>
                <th scope="row">{r.window}</th>
                <td>{modelLabel(r.model)}</td>
                <td>{fmt(r.mae, 3)}</td>
                <td>{fmt(r.mae_ratio, 3)}</td>
                <td>{r.hit_rate === null ? DASH : `${(r.hit_rate * 100).toFixed(0)}%`}</td>
              </tr>
            ))}
          </Table>
        ) : null}
        {p.backtest_h4 ? (
          <p>
            {fmtInt(p.backtest_h4.length)} holdout weeks of forecasts against actual prices (band from{' '}
            {p.backtest_h4[0]?.band_model ?? DASH}).
          </p>
        ) : (
          <Later>
            <p>The holdout forecasts against actual prices arrive at the 04:00 freeze.</p>
          </Later>
        )}
        {p.c1_drivers.length ? <p>c1 adds: {p.c1_drivers.join(', ')}.</p> : null}
        {p.notes.length ? (
          <ul className="problems">
            {p.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        ) : null}
      </Numbers>
    </>
  );
}

// ---- Finding 8 ----

function CurrentForecasts({ nowcast, price }: { nowcast: Status<Nowcast>; price: Status<Price> }) {
  const parts = [
    { name: 'Production: nowcast.json → current', value: nowcast.state === 'ok' ? nowcast.data.current : null },
    { name: 'Price: price.json → current', value: price.state === 'ok' ? price.data.current : null },
  ].filter((part) => part.value !== null && part.value !== undefined);

  if (!parts.length) {
    return (
      <Later title="Optional">
        <p>Only if the back end has time. Nothing yet.</p>
      </Later>
    );
  }
  return (
    <div className="chart-card">
      <p className="unverifiable">
        <IconAlert size={18} /> Unverifiable: these can't be checked before judging.
      </p>
      <p className="note" style={{ margin: '0.5rem 0 1rem' }}>
        00-shared.md doesn't define the format of <code>current</code> yet, so it's shown raw. Ask the back end for its
        shape.
      </p>
      {parts.map((part) => (
        <Numbers key={part.name} title={part.name}>
          <pre className="raw-json">{JSON.stringify(part.value, null, 2)}</pre>
        </Numbers>
      ))}
    </div>
  );
}

// ---- Appendix: area by month ----

function AreaMonthDetails({ rows }: { rows: AreaMonth }) {
  if (!rows.length) {
    return (
      <Later>
        <p>area_month.json has no rows yet.</p>
      </Later>
    );
  }
  const months = [...new Set(rows.map((r) => r.month))].sort();
  const newest = months[months.length - 1]!;
  const areas = new Set(rows.map((r) => r.area)).size;
  const newestRows = rows.filter((r) => r.month === newest).sort((a, b) => a.area - b.area);
  return (
    <Numbers title={`${fmtMonth(newest)} by production area`}>
      <p>
        {fmtInt(rows.length)} rows: {fmtInt(areas)} areas, {months[0]} to {newest}.
      </p>
      <Table caption={`${fmtMonth(newest)} by production area`} head={['Area', 'Harvest', 'Fish', 'Average weight', 'Volume anomaly']}>
        {newestRows.map((r) => (
          <tr key={r.area}>
            <th scope="row">{r.area}</th>
            <td>{fmtTonnes(r.kg)}</td>
            <td>{fmtInt(r.count)}</td>
            <td>{r.avg_kg === null ? DASH : `${fmt(r.avg_kg)} kg`}</td>
            <td>{fmt(r.volume_anom, 3)}</td>
          </tr>
        ))}
      </Table>
    </Numbers>
  );
}
