import type { ReactNode } from 'react';
import { AreaHeatFigure, FACTOR_NAMES, ForecastFigure, PriceForecastFigure, SplitFigure, THIRDS, TrapFigure, logToPct, rise } from '../charts/Figures';
import { Numbers, Pill, Reveal, Table } from '../components/Bits';
import { Boundary } from '../components/Boundary';
import { DASH, fmt, fmtDate, fmtInt, fmtMonth, fmtPct, fmtR, fmtTonnes } from '../components/format';
import { Later, StatusView } from '../components/States';
import { DATA_FILES, type DataKey } from '../data/files';
import { finalLatest, finalScore } from '../data/finalModel';
import type { AreaMonth, Channels, Combined, PriceSisalmoni, Trap } from '../data/schemas';
import type { AllFiles, Source } from '../data/source';
import { FarmSection } from './FarmWeeks';

// The five findings, in page order.

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
      <Finding n={1} id="farms" band="paper" tag="The data" wide scrollTo="farm-map" title="Every farm, every week." lede="Every salmon farm on Norway's coast reports lice, treatments, disease and sea temperature each week. Press play to watch a year go by, read the whole year in the strip under the map, or pick a farm to see its own year.">
        <FarmSection farms={data.farms} index={data.farmWeeksIndex} source={source} />
      </Finding>

      <Finding n={2} id="nowcast" band="cream" tag="The forecast" title="Called before it's published." lede="On the 10th of each month we forecast the month just ended, area by area, using only data public by then. The Directorate publishes around the 20th, so we're about 10 days ahead of the official figure.">
        <StatusView status={data.combined} {...fileProps('combined')}>
          {(c) => (
            <>
              <ForecastFigure c={c} />
              <FinalModelDetails c={c} />
            </>
          )}
        </StatusView>
      </Finding>

      <Finding n={3} id="split" fit band="paper" tag="The harvest" title="More fish, or bigger fish?" lede="Harvest is fish count × average weight. Fast growth gives more and bigger fish; harvests forced early by lice or disease give more but smaller ones. Only the split tells them apart.">
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

      <Finding n={4} id="trap" band="cream" tag="A warning" title="The seasonality trap." lede="Lice, temperature and price all swing with the seasons, so raw correlations look strong. Remove season and trend, and see what's left.">
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

      <Finding n={5} id="price" band="paper" tag="The price" title="The price, weeks ahead." lede="The SISALMONI 3–6 kg index is the reference price for Euronext salmon contracts, in euros per kilo. We forecast it 2 to 8 delivery weeks ahead and compare that with assuming the price stays the same.">
        <StatusView status={data.priceSisalmoni} {...fileProps('priceSisalmoni')}>
          {(p) => <SisalmoniDetails p={p} charts={charts} />}
        </StatusView>
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
  /** Keep the whole section on one screen: on a desktop, the heading sits beside the chart. */
  fit?: boolean;
  children: ReactNode;
};

function Finding({ n, id, band, tag, title, lede, wide = false, scrollTo, fit = false, children }: FindingProps) {
  return (
    <section className={`band band-${band} finding${fit ? ' finding-fit' : ''}`} id={id} aria-labelledby={`${id}-title`} data-scroll-to={scrollTo}>
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

const wholePct = (v: number | null | undefined) => (v == null ? DASH : `${Math.round(v)}%`);

function FinalModelDetails({ c }: { c: Combined }) {
  const tonnes = finalScore(c, 'log_kg');
  const latest = finalLatest(c);
  const [from, to] = c.windows.holdout;
  return (
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
          <h3>Latest checked forecast</h3>
          {latest ? <Pill tone="accent">{fmtMonth(latest.month)}</Pill> : null}
        </div>
        {latest ? (
          <>
            <MiniStats
              items={[
                [`Our forecast, ${latest.areasLabel}`, fmtTonnes(latest.predKg)],
                ['Official figure', fmtTonnes(latest.actualKg)],
                ['How far off', fmtPct(latest.errorPct)],
                ['Forecast made on', fmtDate(latest.madeOn)],
              ]}
            />
            <p className="note card-note">The newest month with an official figure. We made this forecast before that figure came out.</p>
          </>
        ) : null}
      </div>
    </div>
  );
}

// ---- Finding 5 ----

const PRICE_COMPARED: Record<string, string> = { rw: 'Assume no change', old_c1: 'Earlier model with farm data' };

function SisalmoniDetails({ p, charts }: { p: PriceSisalmoni; charts: AllFiles['charts'] }) {
  const { headline, evaluation, display_model: model } = p;
  const actual = charts.price_sisalmoni_v2_actual_vs_predicted;
  const name = (id: string) => (id === model.id ? model.label : PRICE_COMPARED[id] ?? id);
  return (
    <>
      <div className="results-facts">
        <p className="result-fact tone-salmon">
          <strong>€{fmt(headline.mae_eur_per_kg, 2)}</strong>
          <span>average miss per kilo, {evaluation.horizon_delivery_weeks} delivery weeks ahead</span>
        </p>
        <p className="result-fact tone-butter">
          <strong>{wholePct(headline.improvement_vs_no_change_pct)}</strong>
          <span>less error than assuming the price stays the same</span>
        </p>
        <p className="result-fact tone-sky">
          <strong>{wholePct(headline.direction_accuracy_pct)}</strong>
          <span>
            of rises and falls called correctly ({headline.direction_correct} of {headline.direction_calls})
          </span>
        </p>
      </div>
      {actual.state === 'ok' ? <PriceForecastFigure team={actual.data} note={p.uncertainty.must_display} /> : <p className="note">{p.uncertainty.must_display}</p>}
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
