import type { ReactNode } from 'react';
import { Boundary } from '../components/Boundary';
import { DASH, fmt, fmtInt, fmtP, fmtPct, fmtR, fmtTonnes } from '../components/format';
import { Later, StatusView } from '../components/States';
import { VegaChart } from '../components/VegaChart';
import { CHARTS, DATA_FILES, chartPath, type ChartName, type DataKey } from '../data/files';
import type { Status } from '../data/load';
import type { AreaMonth, Channels, Drivers, Nowcast, Price, Trap } from '../data/schemas';
import type { AllFiles, Source } from '../data/source';
import { FarmSection } from './FarmWeeks';
import { FileStatus } from './FileStatus';

// The scaffold page: every finding in the plan's table, under its plain title.
// It exists to test the data flow; the team's design replaces the layout.

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

export function FindingsPage({ files, source }: { files: AllFiles; source: Source }) {
  const { data, charts } = files;
  const chart = (name: ChartName, label: string) => <Chart status={charts[name]} name={name} label={label} />;

  return (
    <>
      <FileStatus files={files} />

      <Finding n={1} id="farms" title="Farm-by-farm weekly picture">
        <FarmSection farms={data.farms} index={data.farmWeeksIndex} source={source} />
      </Finding>

      <Finding
        n={2}
        id="trap"
        title="The seasonality trap"
        intro="Each weekly driver's correlation with price, next to its correlation once season and trend are removed."
      >
        {chart('trap', 'Raw and anomaly correlations of each driver with price')}
        <StatusView status={data.trap} {...fileProps('trap')}>
          {(t) => <TrapTable trap={t} />}
        </StatusView>
      </Finding>

      <Finding
        n={3}
        id="split"
        title="Count × weight split"
        intro="Average fish-count and weight anomalies for each third of lice, temperature, feed and deaths."
      >
        {chart('channels_bins', 'Count and weight anomalies by tercile of each driver')}
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) => <BinsTable bins={c.bins} />}
        </StatusView>
      </Finding>

      <Finding
        n={4}
        id="nowcast"
        title="Production nowcast backtest (F1), with the September 2026 example"
        intro="The Drivers model against baselines B0 and B1, replaying real time: each nowcast uses only data published by the 10th of the next month."
      >
        {chart('nowcast_backtest', 'Nowcast error by model, and national harvest against the nowcast')}
        <StatusView status={data.nowcast} {...fileProps('nowcast')}>
          {(nc) => <NowcastDetails nc={nc} />}
        </StatusView>
      </Finding>

      <Finding
        n={5}
        id="drivers"
        title="Driver ranking"
        intro="How much worse the nowcast gets when each group of drivers is left out. Exploratory: there's no pass mark."
      >
        {chart('drivers_importance', 'Rise in nowcast error without each driver group')}
        <StatusView status={data.drivers} {...fileProps('drivers')}>
          {(d) => <DriversTable d={d} />}
        </StatusView>
      </Finding>

      <Finding
        n={6}
        id="mechanisms"
        title="Mechanism tests M1 and M2"
        intro="M1 (the lice signature) and M2 (growth), with Driscoll–Kraay 95% intervals, pass or fail."
      >
        {chart('channels_panel', 'M1 and M2 coefficient sums with 95% intervals')}
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) =>
            c.panel ? (
              <PanelTable panel={c.panel} />
            ) : (
              <Later>
                <p>
                  M1 and M2 are scored at the 04:00 freeze (the <code>panel</code> part of channels.json).
                </p>
              </Later>
            )
          }
        </StatusView>
      </Finding>

      <Finding
        n={7}
        id="price"
        title="Price backtest (F2)"
        intro="The weekly export price of fresh salmon, forecast weeks ahead, against a random walk."
      >
        {chart('price_scorecard', 'Price forecast error relative to the random walk, by horizon')}
        {chart('price_by_year', 'c0 against c1 error by year')}
        {chart('price_backtest', 'Actual price against the forecasts over the holdout, with a band')}
        <StatusView status={data.price} {...fileProps('price')}>
          {(p) => <PriceDetails p={p} />}
        </StatusView>
      </Finding>

      <Finding
        n={8}
        id="current"
        title="Optional: current forecasts"
        intro="Forecasts from data available now. They can't be checked before judging, so they never replace the backtest."
      >
        <CurrentForecasts nowcast={data.nowcast} price={data.price} />
        {charts.price_fan.state === 'ok' ? (
          <>
            <p className="unverifiable">Unverifiable until after the event.</p>
            <VegaChart spec={charts.price_fan.data} label="Current price forecast" />
          </>
        ) : null}
      </Finding>

      <Finding
        id="area-month"
        title="Harvest and drivers by area and month"
        intro="Not a numbered finding: the monthly table behind the others."
      >
        <StatusView status={data.areaMonth} {...fileProps('areaMonth')}>
          {(rows) => <AreaMonthTable rows={rows} />}
        </StatusView>
      </Finding>
    </>
  );
}

// ---- Building blocks ----

type FindingProps = { n?: number; id: string; title: string; intro?: string; children: ReactNode };

function Finding({ n, id, title, intro, children }: FindingProps) {
  return (
    <section className="finding" id={id} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>
        {n ? <span className="finding-number">{n}.</span> : null} {title}
      </h2>
      {intro ? <p className="intro">{intro}</p> : null}
      <Boundary what={title}>{children}</Boundary>
    </section>
  );
}

function Chart({ status, name, label }: { status: AllFiles['charts'][ChartName]; name: ChartName; label: string }) {
  return (
    <StatusView status={status} file={chartPath(name)} owner={CHARTS[name].owner} due={CHARTS[name].due}>
      {(spec) => <VegaChart spec={spec} label={label} />}
    </StatusView>
  );
}

function Verdict({ pass }: { pass: boolean }) {
  return <strong className={pass ? 'pass' : 'fail'}>{pass ? '✓ Pass' : '✕ Fail'}</strong>;
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

// ---- Finding 2 ----

function TrapTable({ trap }: { trap: Trap }) {
  return (
    <>
      <Table caption={`Correlation with log price, ${trap.from} to ${trap.to}`} head={['Driver', 'Raw', 'Season and trend removed']}>
        {trap.drivers.map((d) => (
          <tr key={d.driver}>
            <th scope="row">
              {d.label}
              {d.driver === trap.highlight ? ' (shown in the chart)' : ''}
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
      <p>
        Development window {nc.windows.dev[0]} to {nc.windows.dev[1]}; holdout {nc.windows.holdout[0]} to{' '}
        {nc.windows.holdout[1]}. Backtest rows: {fmtInt(devRows)} development, {fmtInt(nc.backtest.length - devRows)}{' '}
        holdout.
      </p>
      <ScoresTable caption="Mean absolute error, development window" scores={nc.scores.dev} models={nc.models} />
      {nc.scores.holdout ? (
        <ScoresTable caption="Mean absolute error, holdout" scores={nc.scores.holdout} models={nc.models} />
      ) : (
        <Later>
          <p>Holdout scores arrive at the 04:00 freeze.</p>
        </Later>
      )}
      <p className="note">Actuals: {nc.scores.actuals}.</p>

      <h3>Test F1, judged on the holdout</h3>
      {nc.f1 ? (
        <div className="result">
          <p className="verdict">
            F1: <Verdict pass={nc.f1.pass} />
          </p>
          <dl className="stats">
            <div>
              <dt>MAE, B1</dt>
              <dd>{fmt(nc.f1.mae_b1, 3)}</dd>
            </div>
            <div>
              <dt>MAE, Drivers</dt>
              <dd>{fmt(nc.f1.mae_drivers, 3)}</dd>
            </div>
            <div>
              <dt>Improvement</dt>
              <dd>{fmtPct(nc.f1.improvement_pct)}</dd>
            </div>
            <div>
              <dt>Clark–West</dt>
              <dd>
                {fmt(nc.f1.cw_stat)}, p = {fmtP(nc.f1.cw_p)}
              </dd>
            </div>
          </dl>
        </div>
      ) : (
        <Later>
          <p>F1 is scored once, at the 04:00 freeze. Development-window results never stand in for it.</p>
        </Later>
      )}

      <h3>Worked example: the newest published month</h3>
      {nc.latest ? (
        <LatestExample latest={nc.latest} />
      ) : (
        <Later>
          <p>The worked example arrives at the 04:00 freeze.</p>
        </Later>
      )}
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

function LatestExample({ latest }: { latest: NonNullable<Nowcast['latest']> }) {
  return (
    <>
      <p>
        {latest.month}, as the {modelLabel(latest.model)} model would have nowcast it on {latest.made_on},
        against the Directorate's published figure.
      </p>
      <dl className="stats">
        <div>
          <dt>Nowcast, areas 1–13</dt>
          <dd>{fmtTonnes(latest.national.pred_kg)}</dd>
        </div>
        <div>
          <dt>Published</dt>
          <dd>{fmtTonnes(latest.national.actual_kg)}</dd>
        </div>
        <div>
          <dt>Error</dt>
          <dd>{fmtPct(latest.national.error_pct)}</dd>
        </div>
      </dl>
      <Table caption={`${latest.month} by production area`} head={['Area', 'Nowcast', 'Published', 'Error']}>
        {latest.areas.map((a) => (
          <tr key={a.area}>
            <th scope="row">{a.area}</th>
            <td>{fmtTonnes(a.pred_kg)}</td>
            <td>{fmtTonnes(a.actual_kg)}</td>
            <td>{fmtPct(a.error_pct)}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}

// ---- Finding 5 ----

function DriversTable({ d }: { d: Drivers }) {
  const sorted = [...d.groups].sort((a, b) => (b.increase_pct ?? -Infinity) - (a.increase_pct ?? -Infinity));
  const others = Object.keys(d.by_outcome);
  return (
    <>
      <p>
        {outcomeLabel(d.outcome)}, {d.window}. MAE with every driver: {fmt(d.full_mae, 3)}.
      </p>
      <Table
        caption="Rise in error when each group is left out"
        head={['Group', 'MAE without it', 'Rise in error', ...others.map((o) => `Rise: ${outcomeLabel(o)}`)]}
      >
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
    <Table caption="Sums of lag coefficients" head={['Test', 'Outcome', 'Driver', 'Lags', 'Sum', '95% interval', 'Result']}>
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
          <td>{r.pass === null ? 'No pass mark' : <Verdict pass={r.pass} />}</td>
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
      <p>
        Development window {p.windows.dev[0]} to {p.windows.dev[1]}; holdout {p.windows.holdout[0]} to{' '}
        {p.windows.holdout[1]}. Price history: {fmtInt(p.history.length)} weeks
        {last ? `, latest ${last.week} at ${fmt(last.price_nok_kg)} NOK/kg` : ''}.
      </p>
      {rows.length ? (
        <Table caption={`Scorecard, ${primaryH} weeks ahead`} head={['Window', 'Model', 'MAE', 'vs random walk', 'Direction right']}>
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

      <h3>Test F2, judged on the holdout</h3>
      {p.f2 ? (
        <div className="result">
          <p className="verdict">
            F2: <Verdict pass={p.f2.pass} />
          </p>
          <dl className="stats">
            <div>
              <dt>MAE, c0</dt>
              <dd>{fmt(p.f2.mae_c0, 3)}</dd>
            </div>
            <div>
              <dt>MAE, c1</dt>
              <dd>{fmt(p.f2.mae_c1, 3)}</dd>
            </div>
            <div>
              <dt>Clark–West p</dt>
              <dd>{fmtP(p.f2.cw_p)}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <Later>
          <p>F2 is scored once, at the 04:00 freeze. Development-window results never stand in for it.</p>
        </Later>
      )}
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
        <ul className="notes">
          {p.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
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
    <div className="unverifiable-box">
      <p className="unverifiable">⚠ Unverifiable: these can't be checked before judging.</p>
      <p>
        00-shared.md doesn't define the format of <code>current</code> yet, so it's shown raw. Ask the back
        end for its shape.
      </p>
      {parts.map((part) => (
        <details key={part.name}>
          <summary>{part.name}</summary>
          <pre>{JSON.stringify(part.value, null, 2)}</pre>
        </details>
      ))}
    </div>
  );
}

// ---- Area by month ----

function AreaMonthTable({ rows }: { rows: AreaMonth }) {
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
    <>
      <p>
        {fmtInt(rows.length)} rows: {fmtInt(areas)} areas, {months[0]} to {newest}.
      </p>
      <Table caption={`${newest} by production area`} head={['Area', 'Harvest', 'Fish', 'Average weight', 'Volume anomaly']}>
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
    </>
  );
}
