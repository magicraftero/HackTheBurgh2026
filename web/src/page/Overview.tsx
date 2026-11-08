import type { ReactNode } from 'react';
import { LiveForecast } from '../charts/Figures';
import { monthlyTotals } from '../charts/specs';
import { CountUp, LaterPill, Pill, Reveal, StatTile } from '../components/Bits';
import { DASH, fmtCompact, fmtDate, fmtInt, fmtMonth, fmtMonthShort, fmtPct, fmtTonnes } from '../components/format';
import { IconArrow } from '../components/Icons';
import { describeAreas, finalHeadlines, finalLatest, finalScore } from '../data/finalModel';
import type { Status } from '../data/load';
import type { Combined } from '../data/schemas';
import type { AllFiles } from '../data/source';
import { goTo, isUpcoming } from './Chrome';

// ---- Hero ----

export function Hero({ files }: { files: AllFiles }) {
  return (
    <section className="hero" id="top">
      <div className="container hero-grid">
        <Reveal>
          <h2 id="top-heading" className="display" tabIndex={-1}>
            The harvest, called early.
          </h2>
          <p className="lede">
            Norway publishes what happens in its salmon farms every week. Salmon Signal turns that into an early
            call on each month's harvest and on the salmon price weeks ahead, then proves it on months the models
            never saw.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#current" onClick={(e) => goTo(e, 'current')}>
              See the forecast <IconArrow size={18} />
            </a>
          </div>
          <p className="footnote">
            Data: Norwegian Directorate of Fisheries, BarentsWatch, Statistics Norway and Norges Bank.
          </p>
        </Reveal>
        <Reveal>
          <WorkedExampleCard status={files.data.combined} />
        </Reveal>
      </div>
      <ScaleStrip files={files} />
    </section>
  );
}

function WorkedExampleCard({ status }: { status: AllFiles['data']['combined'] }) {
  const latest = status.state === 'ok' ? finalLatest(status.data) : null;
  if (!latest) {
    return (
      <div className="example-card">
        <div className="example-top">
          <span className="example-title">Latest checked forecast</span>
          {status.state === 'loading' ? null : <LaterPill>Coming soon</LaterPill>}
        </div>
        <span className="skeleton" style={{ height: '4.5rem', width: '62%' }} />
        <p className="example-label">
          The newest published month, nowcast with only the data public at the time, against the official
          figure.
        </p>
      </div>
    );
  }
  return (
    <div className="example-card">
      <div className="example-top">
        <span className="example-title">Latest checked forecast</span>
        <Pill tone="accent">{fmtMonth(latest.month)}</Pill>
      </div>
      <p className="hero-figure">{fmtPct(latest.errorPct)}</p>
      <p className="example-label">
        Forecast error for {fmtMonth(latest.month)}, {latest.areasLabel}
      </p>
      <dl className="example-rows">
        <div>
          <dt>Our forecast</dt>
          <dd>{fmtTonnes(latest.predKg)}</dd>
        </div>
        <div>
          <dt>Published figure</dt>
          <dd>{fmtTonnes(latest.actualKg)}</dd>
        </div>
        <div>
          <dt>Called on</dt>
          <dd>{fmtDate(latest.madeOn)}</dd>
        </div>
      </dl>
      <p className="example-foot">
        Made with only the data public on that day, then checked against the Directorate's release.
      </p>
    </div>
  );
}

// ---- Scale strip (the foot of the hero) ----

function tileValue(status: Status<unknown>, value: number | null): { value: ReactNode; pill?: ReactNode } {
  if (status.state === 'loading') return { value: DASH };
  if (status.state !== 'ok' || value === null) return { value: DASH, pill: <LaterPill>Coming soon</LaterPill> };
  return { value: <CountUp value={value} format={fmtCompact} /> };
}

// price/experiments/sisalmoni/SOURCES.md: 2024-W32 to 2026-W44. The display file doesn't carry the whole history.
const SISALMONI_WEEKS = 117;

function ScaleStrip({ files }: { files: AllFiles }) {
  const { farms, farmWeeksIndex, priceSisalmoni } = files.data;
  const farmList = farms.state === 'ok' ? farms.data : null;
  const years = farmWeeksIndex.state === 'ok' ? [...farmWeeksIndex.data.years].sort((a, b) => a - b) : null;

  const tiles = [
    {
      label: 'Farms tracked',
      ...tileValue(farms, farmList ? farmList.length : null),
      note: 'Every site in the register',
    },
    {
      label: 'Production areas',
      ...tileValue(farms, farmList ? new Set(farmList.map((f) => f.area)).size : null),
      note: 'Along the coast, south to north',
    },
    {
      label: 'Years of weekly farm data',
      ...tileValue(farmWeeksIndex, years ? years.length : null),
      note: years?.length ? `${years[0]} to ${years[years.length - 1]}` : 'Lice, treatments, temperature',
    },
    {
      label: 'Weeks of SISALMONI prices',
      ...tileValue(priceSisalmoni, priceSisalmoni.state === 'ok' ? SISALMONI_WEEKS : null),
      note: 'Aug 2024 to Oct 2026, euros per kilo',
    },
  ];

  return (
    <section className="container scale-strip" aria-labelledby="scale-title">
      <Reveal>
        <h2 id="scale-title">Built on every farm, every week.</h2>
        <div className="scale-tiles">
          {tiles.map((t) => (
            <StatTile key={t.label} className="scale-tile" label={t.label} value={t.value} note={t.note} pill={t.pill} tone="salmon" />
          ))}
        </div>
      </Reveal>
    </section>
  );
}

// ---- Results band ----

// Plain names for the contract's driver and outcome codes (raw codes stay in the tables).
/** The forecast nobody can check yet: the headline of the section. */
function NextForecast({ files }: { files: AllFiles }) {
  const { farmerActions } = files.data;
  if (farmerActions.state !== 'ok') {
    return (
      <div className="forecast-card">
        <p className="forecast-card-label">Our next forecast</p>
        <p className="forecast-card-number">{DASH}</p>
        {farmerActions.state === 'loading' ? null : (
          <div className="forecast-card-foot">
            <LaterPill>Coming soon</LaterPill>
          </div>
        )}
      </div>
    );
  }
  const f = farmerActions.data;
  return (
    <div className="forecast-card">
      <p className="forecast-card-label">Our forecast for {fmtMonth(f.target_month)}</p>
      <p className="forecast-card-number">{f.national.kg === null ? DASH : fmtInt(f.national.kg / 1000)}</p>
      <p className="forecast-card-unit">
        tonnes of salmon harvested, <span>{describeAreas(f.national.areas)}</span>
      </p>
      <div className="forecast-card-foot forecast-card-dates">
        <span>Forecast made on {fmtDate(f.made_on)}</span>
        <span>
          {isUpcoming(f.publishes_around)
            ? `Official figure due around ${fmtDate(f.publishes_around)}, so it can't be checked yet`
            : `The official figure was due around ${fmtDate(f.publishes_around)}`}
        </span>
      </div>
    </div>
  );
}

/** "0.7% high" or "3.3% low": how far a forecast was from the official figure. */
function howClose(forecast: number, published: number): string {
  const pct = (forecast / published - 1) * 100;
  return `${Math.abs(pct).toFixed(1)}% ${pct >= 0 ? 'high' : 'low'}`;
}

/** The newest months with an official figure, newest first. */
function RecentForecasts({ c, areasLabel }: { c: Combined; areasLabel: string }) {
  const rows = monthlyTotals(c)
    .filter((t) => t.window === 'holdout')
    .slice(-5)
    .reverse();
  return (
    <div className="results-table-card">
      <h3>How close we've been</h3>
      <table className="results-table">
        <caption className="sr-only">Our forecast of the total harvest, {areasLabel}, against the official figure, for the latest months</caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">We forecast</th>
            <th scope="col">Official figure</th>
            <th scope="col">We were</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.month}>
              <th scope="row">{fmtMonthShort(t.month)}</th>
              <td>
                {fmtInt(t.forecast / 1000)}
                <span className="results-unit"> t</span>
              </td>
              <td>
                {fmtInt(t.published / 1000)}
                <span className="results-unit"> t</span>
              </td>
              <td className="results-close">{howClose(t.forecast, t.published)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="results-table-foot">
        <span>Total harvest in tonnes, {areasLabel}</span>
        <a href="#nowcast" onClick={(e) => goTo(e, 'nowcast')}>
          See every month <IconArrow size={16} />
        </a>
      </p>
    </div>
  );
}

export function ResultsBand({ files }: { files: AllFiles }) {
  const { combined } = files.data;
  const c = combined.state === 'ok' ? combined.data : null;
  const tonnes = c ? finalScore(c, 'log_kg') : null;
  const size = c ? finalScore(c, 'log_avg_kg') : null;
  const headlines = c ? finalHeadlines(c) : null;
  const shown = (pct: number | undefined) => (pct === undefined ? DASH : `${Math.round(pct)}%`);

  return (
    <section className="band band-paper" id="results" aria-labelledby="results-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="results-title">The results.</h2>
            <p className="lede">Our forecast of Norway's salmon harvest, about 10 days before the official figures, and how close it has come.</p>
          </div>
        </Reveal>
        <div className="results-lead results-lead-table">
          {c && headlines ? (
            <RecentForecasts c={c} areasLabel={headlines.areasLabel} />
          ) : (
            <div className="results-table-card">
              <h3>How close we've been</h3>
              {combined.state === 'loading' ? null : <LaterPill>Coming soon</LaterPill>}
            </div>
          )}
          <div className="results-facts">
            <p className="result-fact tone-salmon">
              <strong>{shown(headlines?.totalAccuracyPct)}</strong>
              <span>accurate on the total harvest{headlines ? `, ${headlines.areasLabel}` : ''}</span>
            </p>
            <p className="result-fact tone-butter">
              <strong>{shown(tonnes?.accuracyPct)}</strong>
              <span>accurate on each area's tonnes</span>
            </p>
            <p className="result-fact tone-sky">
              <strong>{shown(size?.accuracyPct)}</strong>
              <span>accurate on fish size</span>
            </p>
          </div>
        </div>
        {c && headlines ? (
          <p className="results-caption">
            Tested on {fmtInt(headlines.forecasts)} forecasts from {fmtMonth(c.windows.holdout[0])} to {fmtMonth(c.windows.holdout[1])}, each using only
            data public at the time. Accuracy is 100% minus the average miss.{' '}
            <a href="#nowcast" onClick={(e) => goTo(e, 'nowcast')}>
              How we tested it
            </a>
          </p>
        ) : null}
      </div>
    </section>
  );
}

// ---- Next forecast ----

export function NextForecastBand({ files }: { files: AllFiles }) {
  const { farmerActions } = files.data;
  return (
    <section className="band band-cream" id="current" aria-labelledby="current-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="current-title">Next forecast.</h2>
            <p className="lede">Our forecast for the latest month, made before the official figure is published.</p>
          </div>
        </Reveal>
        <div className="results-lead">
          <NextForecast files={files} />
          {farmerActions.state === 'ok' ? <LiveForecast f={farmerActions.data} /> : <div className="chart-card" />}
        </div>
      </div>
    </section>
  );
}
