import { useMemo, type ReactNode } from 'react';
import { AreaHeatFigure, DRIVER_LABELS, FACTOR_NAMES, ForecastFigure, LiveForecast, MechanismFigure, OUTCOME_LABELS, RankingFigure, SplitFigure, THIRDS, TrapFigure, logToPct, rise } from '../charts/Figures';
import { PRICE_MODELS } from '../charts/specs';
import { LaterPill, Numbers, PassPill, Pill, Reveal, Table } from '../components/Bits';
import { Boundary } from '../components/Boundary';
import { DASH, fmt, fmtDate, fmtInt, fmtMonth, fmtP, fmtPct, fmtR, fmtTonnes } from '../components/format';
import { IconAlert } from '../components/Icons';
import { Later, StatusView } from '../components/States';
import { VegaChart } from '../components/VegaChart';
import { DATA_FILES, type DataKey } from '../data/files';
import { finalLatest, finalScore } from '../data/finalModel';
import type { AreaMonth, ChartSpec, Channels, Combined, Drivers, Nowcast, Price, PriceSisalmoni, Trap } from '../data/schemas';
import type { AllFiles, Source } from '../data/source';
import { FarmSection } from './FarmWeeks';

// The eight findings, in the order the plan set out.

const OUTCOMES: Record<string, string> = {
  log_kg: 'Harvest (tonnes)',
  log_count: 'Fish count',
  log_avg_kg: 'Average weight',
};
const MODELS: Record<string, string> = {
  b0: 'Season and stock',
  b1: 'Stock and exports (baseline)',
  drivers: 'All farm data',
  rw: 'Random walk',
  ...PRICE_MODELS,
};
const outcomeLabel = (o: string) => OUTCOMES[o] ?? o;
const modelLabel = (m: string) => MODELS[m] ?? m;
const fmtWeek = (w: string) => `week ${Number(w.slice(6))} of ${w.slice(0, 4)}`;

const fileProps = (key: DataKey) => ({
  file: DATA_FILES[key].path.replace(/^data\//, ''),
  owner: DATA_FILES[key].owner,
  due: DATA_FILES[key].due,
});

export function Findings({ files, source }: { files: AllFiles; source: Source }) {
  const { data, charts } = files;

  return (
    <>
      <Finding n={1} id="farms" band="cream" tag="The data" wide scrollTo="farm-map" title="Every farm, every week." lede="Every salmon farm on Norway's coast reports lice, treatments, disease and sea temperature each week. Press play to watch a year go by, read the whole year in the strip under the map, or pick a farm to see its own year.">
        <FarmSection farms={data.farms} index={data.farmWeeksIndex} source={source} />
      </Finding>

      <Finding n={2} id="nowcast" band="paper" tag="The forecast" title="Called before it's published." lede="On the 10th of each month we forecast the month just ended, area by area, using only data public by then. The Directorate publishes around the 20th, so we're about 10 days ahead of the official figure.">
        <StatusView status={data.combined} {...fileProps('combined')}>
          {(c) => (
            <>
              <ForecastFigure c={c} />
              <FinalModelDetails c={c} />
            </>
          )}
        </StatusView>
        <StatusView status={data.nowcast} {...fileProps('nowcast')}>
          {(nc) => <FirstModelDetails nc={nc} />}
        </StatusView>
      </Finding>

      <Finding n={3} id="split" band="cream" tag="The harvest" title="More fish, or bigger fish?" lede="Harvest is fish count × average weight. Fast growth gives more and bigger fish; harvests forced early by lice or disease give more but smaller ones. Only the split tells them apart.">
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) => (
            <>
              <SplitFigure bins={c.bins} />
              <Numbers>
                <BinsTable bins={c.bins} />
              </Numbers>
            </>
          )}
        </StatusView>
      </Finding>

      <Finding n={4} id="trap" band="paper" tag="A warning" title="The seasonality trap." lede="Lice, temperature and price all swing with the seasons, so raw correlations look strong. Remove season and trend, and see what's left.">
        <StatusView status={data.trap} {...fileProps('trap')}>
          {(t) => (
            <>
              <TrapFigure trap={t} />
              <Numbers>
                <TrapTable trap={t} />
              </Numbers>
            </>
          )}
        </StatusView>
      </Finding>

      <Finding n={5} id="drivers" band="cream" tag="The drivers" title="What drives it." lede="Take each group of factors out of the forecast and measure how much worse it gets. Stock decides how much salmon comes out. Deaths, disease and lice matter more for what size it is.">
        <StatusView status={data.drivers} {...fileProps('drivers')}>
          {(d) => (
            <>
              <RankingFigure d={d} />
              <Numbers>
                <DriversTable d={d} />
              </Numbers>
            </>
          )}
        </StatusView>
      </Finding>

      <Finding n={6} id="mechanisms" band="paper" tag="The biology · tests M1, M2" title="How lice and warmth move the harvest." lede="M1, the lice signature: do lice bring harvests forward, with more but smaller fish? M2, growth: does warmer water grow heavier fish? Each with a 95% interval, pass or fail.">
        <StatusView status={data.channels} {...fileProps('channels')}>
          {(c) =>
            c.panel ? (
              <>
                <MechanismFigure panel={c.panel} />
                <Numbers>
                  <PanelTable panel={c.panel} />
                </Numbers>
              </>
            ) : (
              <Later />
            )
          }
        </StatusView>
      </Finding>

      <Finding n={7} id="price" band="cream" tag="The price" title="The price, weeks ahead." lede="The SISALMONI 3–6 kg index is the reference price for Euronext salmon contracts, in euros per kilo. We forecast it 2 to 8 delivery weeks ahead and compare that with assuming the price stays the same.">
        <StatusView status={data.priceSisalmoni} {...fileProps('priceSisalmoni')}>
          {(p) => <SisalmoniDetails p={p} charts={charts} />}
        </StatusView>
        <StatusView status={data.price} {...fileProps('price')}>
          {(p) => <PriceDetails p={p} />}
        </StatusView>
      </Finding>

      <Finding n={8} id="current" band="paper" tag="Live" title="Right now." lede="Our forecast for the latest month, made before the official figure is published.">
        <StatusView status={data.farmerActions} {...fileProps('farmerActions')}>
          {(f) => <LiveForecast f={f} />}
        </StatusView>
        {charts.price_fan.state === 'ok' ? (
          <div className="chart-card">
            <p className="unverifiable">
              <IconAlert size={18} /> Can't be checked until after the event
            </p>
            <TeamChart spec={charts.price_fan.data} label="Current price forecast" bare />
          </div>
        ) : null}
      </Finding>

      <Finding id="area-month" band="cream" tag="Appendix" title="Harvest by area and month." lede="The monthly table behind the other findings.">
        <StatusView status={data.areaMonth} {...fileProps('areaMonth')}>
          {(rows) => (
            <>
              <AreaHeatFigure rows={rows} />
              <AreaMonthDetails rows={rows} />
            </>
          )}
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
  /** Let the body run wider than the page column on big screens (the farm map). */
  wide?: boolean;
  /** An element inside the section that links to it should land on instead (see goTo). */
  scrollTo?: string;
  children: ReactNode;
};

function Finding({ n, id, band, tag, title, lede, wide = false, scrollTo, children }: FindingProps) {
  return (
    <section className={`band band-${band} finding`} id={id} aria-labelledby={`${id}-title`} data-scroll-to={scrollTo}>
      <div className={`container${wide ? ' container-wide' : ''}`}>
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

/** A chart file from the team, shown without its own title, as wide as the card. */
function TeamChart({ spec, label, bare = false }: { spec: ChartSpec; label: string; bare?: boolean }) {
  const shown = useMemo(() => {
    const { title: _title, ...rest } = spec;
    return 'width' in rest ? { ...rest, width: 'container', autosize: { type: 'fit-x', contains: 'padding' } } : rest;
  }, [spec]);
  const chart = <VegaChart spec={shown as ChartSpec} label={label} />;
  return bare ? chart : <div className="chart-card">{chart}</div>;
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

// ---- Finding 4 ----

function TrapTable({ trap }: { trap: Trap }) {
  return (
    <>
      <Table caption={`Correlation with the salmon price, ${fmtWeek(trap.from)} to ${fmtWeek(trap.to)}`} head={['Factor', 'Raw', 'Season and trend removed']}>
        {trap.drivers.map((d) => (
          <tr key={d.driver}>
            <th scope="row">
              {d.label}
            </th>
            <td>{fmtR(d.raw_r)}</td>
            <td>{fmtR(d.anom_r)}</td>
          </tr>
        ))}
      </Table>
      <p className="note">{fmtInt(trap.series.length)} weeks of data.</p>
    </>
  );
}

// ---- Finding 3 ----

function BinsTable({ bins }: { bins: Channels['bins'] }) {
  return (
    <Table caption="Harvest after low, middle and high months, against normal for the time of year" head={['Factor', 'Months later', 'Third of months', 'Fish harvested', 'Average weight', 'Area-months']}>
      {bins.map((b) => (
        <tr key={`${b.driver}-${b.tercile}`}>
          <th scope="row">{FACTOR_NAMES[b.driver] ?? b.driver}</th>
          <td>{b.window.replace('-', ' to ')}</td>
          <td>{THIRDS[b.tercile] ?? b.tercile}</td>
          <td>{rise(logToPct(b.count_anom))}</td>
          <td>{rise(logToPct(b.weight_anom))}</td>
          <td>{fmtInt(b.n)}</td>
        </tr>
      ))}
    </Table>
  );
}

// ---- Finding 2 ----

const FINAL_MODELS = [
  ['b1', 'Baseline (B1)'],
  ['drivers', 'All farm data'],
  ['ml', 'Machine learning'],
  ['blend', 'Machine-learning blend'],
  ['combined', 'Our forecast'],
] as const;

const wholePct = (v: number | undefined) => (v === undefined ? DASH : `${Math.round(v)}%`);

function FinalModelDetails({ c }: { c: Combined }) {
  const tonnes = finalScore(c, 'log_kg');
  const latest = finalLatest(c);
  const [from, to] = c.windows.holdout;
  return (
    <>
      <div className="split-2">
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>How accurate it was</h3>
            <Pill tone="accent">
              {fmtMonth(from)} to {fmtMonth(to)}
            </Pill>
          </div>
          <MiniStats
            items={[
              ['Accuracy, tonnes', wholePct(tonnes?.accuracyPct)],
              ['Accuracy, fish count', wholePct(finalScore(c, 'log_count')?.accuracyPct)],
              ['Accuracy, fish size', wholePct(finalScore(c, 'log_avg_kg')?.accuracyPct)],
              ['Less error than our baseline model', wholePct(tonnes?.lessErrorPct)],
            ]}
          />
        </div>
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>Worked example</h3>
            {latest ? <Pill tone="accent">{fmtMonth(latest.month)}</Pill> : null}
          </div>
          {latest ? (
            <MiniStats
              items={[
                [`Forecast, ${latest.areasLabel}`, fmtTonnes(latest.predKg)],
                ['Published', fmtTonnes(latest.actualKg)],
                ['Error', fmtPct(latest.errorPct)],
                ['Called on', fmtDate(latest.madeOn)],
              ]}
            />
          ) : null}
        </div>
      </div>
      <Numbers>
        <p>
          Tonnes come from Statistics Norway's weekly export figures, split across areas and averaged with our baseline
          model, which uses the season, the fish in the water and exports. Fish size comes from our machine-learning
          model, and fish count is tonnes divided by fish size.
          Accuracy is 100% minus the typical error in log points. Areas 1 and 13 harvest too irregularly to forecast.
          We designed this forecast on 2021–2024 after our first model missed its mark and the later months had been
          opened, so it isn't one of the tests we set in advance.
        </p>
        <FinalScoresTable caption={`Typical error in log points, ${fmtMonth(from)} to ${fmtMonth(to)}`} scores={c.scores.holdout} />
        <FinalScoresTable caption={`Typical error in log points, ${fmtMonth(c.windows.dev[0])} to ${fmtMonth(c.windows.dev[1])}`} scores={c.scores.dev} />
        {latest ? (
          <Table caption={`${fmtMonth(latest.month)} by production area`} head={['Area', 'Forecast', 'Published', 'Error']}>
            {latest.areas.map((a) => (
              <tr key={a.area}>
                <th scope="row">{a.area}</th>
                <td>{fmtTonnes(a.predKg)}</td>
                <td>{fmtTonnes(a.actualKg)}</td>
                <td>{fmtPct(a.errorPct)}</td>
              </tr>
            ))}
          </Table>
        ) : null}
      </Numbers>
    </>
  );
}

function FinalScoresTable({ caption, scores }: { caption: string; scores: Combined['scores']['holdout'] }) {
  return (
    <Table caption={caption} head={['Outcome', ...FINAL_MODELS.map(([, label]) => label)]}>
      {Object.entries(scores).map(([outcome, row]) => (
        <tr key={outcome}>
          <th scope="row">{outcomeLabel(outcome)}</th>
          {FINAL_MODELS.map(([model]) => (
            <td key={model}>{fmt(row?.[model], 3)}</td>
          ))}
        </tr>
      ))}
    </Table>
  );
}

function FirstModelDetails({ nc }: { nc: Nowcast }) {
  const devRows = nc.backtest.filter((r) => r.window === 'dev').length;
  return (
    <Numbers title="Our first model, and the test it missed">
      <div className="split-2">
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>Test F1: farm data cuts error by 5%</h3>
            {nc.f1 ? <PassPill pass={nc.f1.pass} /> : <LaterPill>Coming soon</LaterPill>}
          </div>
          {nc.f1 ? (
            <MiniStats
              items={[
                ['Error, baseline', fmt(nc.f1.mae_b1, 3)],
                ['Error, with farm data', fmt(nc.f1.mae_drivers, 3)],
                ['Improvement', fmtPct(nc.f1.improvement_pct)],
                ['Clark–West p', fmtP(nc.f1.cw_p)],
              ]}
            />
          ) : (
            <p className="note">This test hasn't been scored yet.</p>
          )}
        </div>
        <div className="chart-card">
          <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h3>Worked example</h3>
            {nc.latest ? <Pill tone="accent">{fmtMonth(nc.latest.month)}</Pill> : <LaterPill>Coming soon</LaterPill>}
          </div>
          {nc.latest ? (
            <MiniStats
              items={[
                ['Forecast, areas 1–13', fmtTonnes(nc.latest.national.pred_kg)],
                ['Published', fmtTonnes(nc.latest.national.actual_kg)],
                ['Error', fmtPct(nc.latest.national.error_pct)],
                ['Called on', fmtDate(nc.latest.made_on)],
              ]}
            />
          ) : (
            <p className="note">Not published yet.</p>
          )}
        </div>
      </div>
      <p>
        Built on {fmtMonth(nc.windows.dev[0])} to {fmtMonth(nc.windows.dev[1])}, tested on {fmtMonth(nc.windows.holdout[0])} to{' '}
        {fmtMonth(nc.windows.holdout[1])}: {fmtInt(devRows)} area-months to build on and {fmtInt(nc.backtest.length - devRows)} to test.
        Published figures are the latest revised ones, not first releases.
      </p>
      <ScoresTable caption="Typical error in log points, the months it was built on" scores={nc.scores.dev} models={nc.models} />
      {nc.scores.holdout ? <ScoresTable caption="Typical error in log points, the months it never saw" scores={nc.scores.holdout} models={nc.models} /> : null}
      {nc.latest ? (
        <Table caption={`${fmtMonth(nc.latest.month)} by production area, first model`} head={['Area', 'Forecast', 'Published', 'Error']}>
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
        {outcomeLabel(d.outcome)}, {d.window.split(' to ').map(fmtMonth).join(' to ')}. Typical error with every factor in: {fmt(d.full_mae, 3)}.
      </p>
      <Table caption="Rise in error when each group is left out" head={['Factor', 'Error without it', 'Rise in error', ...others.map((o) => `Rise: ${outcomeLabel(o)}`)]}>
        {sorted.map((g) => (
          <tr key={g.group}>
            <th scope="row">{g.label}</th>
            <td>{fmt(g.mae_without, 3)}</td>
            <td>{rise(g.increase_pct)}</td>
            {others.map((o) => (
              <td key={o}>{rise(d.by_outcome[o]?.find((x) => x.group === g.group)?.increase_pct ?? null)}</td>
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
    <Table caption="Sums of lag coefficients, with 95% intervals" head={['Test', 'Outcome', 'Factor', 'Months later', 'Sum', '95% interval', 'Result']}>
      {panel.map((r, i) => (
        <tr key={`${r.test}-${r.outcome}-${r.driver}-${i}`}>
          <th scope="row">{r.test}</th>
          <td>{OUTCOME_LABELS[r.outcome] ?? r.outcome}</td>
          <td>{DRIVER_LABELS[r.driver] ?? r.driver}</td>
          <td>{r.lags.replace('-', ' to ')}</td>
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

const PRICE_DRIVERS: Record<string, string> = {
  mobile_anom: 'lice',
  treat_anom: 'treatments',
  disease_share: 'disease',
  dd_below8: 'sea temperature under 8 °C',
  dd_8to14: 'sea temperature from 8 to 14 °C',
  dd_above14: 'sea temperature over 14 °C',
  biomass_anom: 'biomass',
  feed_rate_anom: 'feed',
  mortality_anom: 'deaths',
  usdnok_chg: 'the dollar exchange rate',
};

/** The notes in price.json that are for readers, not the team's build log. */
const publicNotes = (notes: string[]) => notes.filter((n) => !/branch|freeze|engine|locked|BIC|Rebuild|integration|MAE/i.test(n));

const PRICE_COMPARED: Record<string, string> = { rw: 'Assume no change', old_c1: 'Earlier model with farm data' };
const pct1 = (v: number | null) => (v === null ? DASH : `${v.toFixed(1)}%`);

function SisalmoniDetails({ p, charts }: { p: PriceSisalmoni; charts: AllFiles['charts'] }) {
  const { headline, evaluation, display_model: model } = p;
  const actual = charts.price_sisalmoni_v2_actual_vs_predicted;
  const errors = charts.price_sisalmoni_v2_forecast_errors;
  const name = (id: string) => (id === model.id ? model.label : PRICE_COMPARED[id] ?? id);
  return (
    <>
      <div className="chart-card">
        <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3>{evaluation.horizon_delivery_weeks} delivery weeks ahead</h3>
          <Pill tone="partial">{p.status_label}</Pill>
        </div>
        <MiniStats
          items={[
            ['Average miss, per kilo', `€${fmt(headline.mae_eur_per_kg, 2)}`],
            ['Less error than assuming no change', pct1(headline.improvement_vs_no_change_pct)],
            ['Less error than our earlier model with farm data', pct1(headline.improvement_vs_original_biology_pct)],
            ['Rise or fall called correctly', `${pct1(headline.direction_accuracy_pct)} (${headline.direction_correct} of ${headline.direction_calls})`],
          ]}
        />
        <p className="note">{p.uncertainty.must_display}</p>
      </div>
      {actual.state === 'ok' ? <TeamChart spec={actual.data} label="The actual SISALMONI price against the forecasts" /> : null}
      {errors.state === 'ok' ? <TeamChart spec={errors.data} label="Forecast error each week" /> : null}
      <Numbers>
        <p>
          {fmtInt(evaluation.forecasts)} forecasts, for delivery from {fmtDate(evaluation.target_dates[0])} to {fmtDate(evaluation.target_dates[1])}.{' '}
          {evaluation.horizon_note} The model uses: {model.features.join(', ')}.
          {p.recommendation.recommended_live_model_id === 'rw' ? ' Assuming no change is still our recommended default for live use.' : ''}
        </p>
        <Table caption={`Average miss ${evaluation.horizon_delivery_weeks} delivery weeks ahead, euros per kilo`} head={['Model', 'Average miss', 'Forecasts']}>
          {p.comparisons.map((c) => (
            <tr key={c.model}>
              <th scope="row">{name(c.model)}</th>
              <td>{fmt(c.mae_eur_kg, 3)}</td>
              <td>{fmtInt(c.n)}</td>
            </tr>
          ))}
        </Table>
        <Table caption="Average miss by delivery weeks ahead, euros per kilo" head={['Delivery weeks ahead', model.label, PRICE_COMPARED.rw!, PRICE_COMPARED.old_c1!]}>
          {p.secondary_horizons.map((h) => (
            <tr key={h.horizon_delivery_weeks}>
              <th scope="row">{h.horizon_delivery_weeks}</th>
              <td>{fmt(h.selected_ridge_mae_eur_kg, 3)}</td>
              <td>{fmt(h.no_change_mae_eur_kg, 3)}</td>
              <td>{fmt(h.original_biology_mae_eur_kg, 3)}</td>
            </tr>
          ))}
        </Table>
      </Numbers>
    </>
  );
}

function PriceDetails({ p }: { p: Price }) {
  const primaryH = p.cw.find((c) => c.primary)?.h ?? null;
  const rows = primaryH === null ? [] : p.scorecard.filter((r) => r.h === primaryH);
  const last = p.history[p.history.length - 1];
  return (
    <Numbers title="Our earlier test on the export price (F2)">
      <div className="chart-card">
        <div className="verdict-row" style={{ justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h3>Test F2: farm data improves the four-week forecast</h3>
          {p.f2 ? <PassPill pass={p.f2.pass} /> : <LaterPill>Coming soon</LaterPill>}
        </div>
        {p.f2 ? (
          <MiniStats
            items={[
              ['Error, without farm data', fmt(p.f2.mae_c0, 3)],
              ['Error, with farm data', fmt(p.f2.mae_c1, 3)],
              ['Clark–West p', fmtP(p.f2.cw_p)],
              ['Latest price', last ? `${fmt(last.price_nok_kg)} NOK/kg` : DASH],
            ]}
          />
        ) : (
          <p className="note">This test hasn't been scored yet.</p>
        )}
      </div>
      <p>
        This older test used Norway's export price in kroner per kilo, a different price from the SISALMONI index above.
        Built on {fmtWeek(p.windows.dev[0])} to {fmtWeek(p.windows.dev[1])}. Price history: {fmtInt(p.history.length)} weeks
        {last ? `, latest ${fmtWeek(last.week)} at ${fmt(last.price_nok_kg)} NOK per kg` : ''}.
      </p>
      {rows.length ? (
        <Table caption={`Scorecard, ${primaryH} weeks ahead`} head={['Period', 'Model', 'Error', 'vs random walk', 'Direction right']}>
          {rows.map((r) => (
            <tr key={`${r.window}-${r.model}`}>
              <th scope="row">{r.window === 'dev' ? 'Built on' : 'Never seen'}</th>
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
          {fmtInt(p.backtest_h4.length)} test weeks of forecasts against actual prices.
        </p>
      ) : null}
      {p.c1_drivers.length ? <p>The farm data added: {p.c1_drivers.map((d) => PRICE_DRIVERS[d] ?? d.replace(/_/g, ' ')).join(', ')}.</p> : null}
      {publicNotes(p.notes).length ? (
        <ul className="problems">
          {publicNotes(p.notes).map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </Numbers>
  );
}

// ---- Appendix: area by month ----

function AreaMonthDetails({ rows }: { rows: AreaMonth }) {
  if (!rows.length) {
    return <Later />;
  }
  const months = [...new Set(rows.map((r) => r.month))].sort();
  const newest = months[months.length - 1]!;
  const areas = new Set(rows.map((r) => r.area)).size;
  const newestRows = rows.filter((r) => r.month === newest).sort((a, b) => a.area - b.area);
  return (
    <Numbers title={`${fmtMonth(newest)} by production area`}>
      <p>
        {fmtInt(rows.length)} area-months: {fmtInt(areas)} areas, {fmtMonth(months[0]!)} to {fmtMonth(newest)}.
      </p>
      <Table caption={`${fmtMonth(newest)} by production area`} head={['Area', 'Harvest', 'Fish', 'Average weight', 'Against normal']}>
        {newestRows.map((r) => (
          <tr key={r.area}>
            <th scope="row">{r.area}</th>
            <td>{fmtTonnes(r.kg)}</td>
            <td>{fmtInt(r.count)}</td>
            <td>{r.avg_kg === null ? DASH : `${fmt(r.avg_kg)} kg`}</td>
            <td>{rise(logToPct(r.volume_anom))}</td>
          </tr>
        ))}
      </Table>
    </Numbers>
  );
}
