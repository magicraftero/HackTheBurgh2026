import type { ReactNode } from 'react';
import { CountUp, LaterPill, PartialPill, PassPill, Pill, ReadyPill, Reveal, StatTile } from '../components/Bits';
import { DASH, fmtCompact, fmtDate, fmtMonth, fmtPct, fmtTonnes } from '../components/format';
import { IconArrow } from '../components/Icons';
import type { Status } from '../data/load';
import type { AllFiles } from '../data/source';
import { REPO, goTo } from './Chrome';

// ---- Hero ----

export function Hero({ files }: { files: AllFiles }) {
  return (
    <section className="hero" id="top">
      <div className="container hero-grid">
        <Reveal>
          <p className="eyebrow">
            <Pill tone="accent">HackTheBurgh XIII · Edinburgh</Pill>
          </p>
          <h1 id="top-heading" tabIndex={-1}>
            The harvest, called early.
          </h1>
          <p className="lede">
            Norway publishes what happens in its salmon farms every week. Salmon Signal turns that into an early
            call on each month's harvest and on the export price weeks ahead, then proves it on months the models
            never saw.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#nowcast" onClick={(e) => goTo(e, 'nowcast')}>
              See the forecast <IconArrow size={18} />
            </a>
            <a className="btn btn-secondary" href="#prereg" onClick={(e) => goTo(e, 'prereg')}>
              How we tested it
            </a>
          </div>
          <p className="footnote">
            Data: Norwegian Directorate of Fisheries, BarentsWatch, Statistics Norway and Norges Bank.
          </p>
        </Reveal>
        <Reveal>
          <WorkedExampleCard status={files.data.nowcast} />
        </Reveal>
      </div>
    </section>
  );
}

function WorkedExampleCard({ status }: { status: AllFiles['data']['nowcast'] }) {
  const latest = status.state === 'ok' ? status.data.latest : null;
  if (!latest) {
    return (
      <div className="example-card">
        <div className="example-top">
          <span className="example-title">Worked example</span>
          {status.state === 'loading' ? null : <LaterPill>Arrives 04:00</LaterPill>}
        </div>
        <span className="skeleton" style={{ height: '4.5rem', width: '62%' }} />
        <p className="example-label">
          The newest published month, nowcast with only the data public at the time, against the official
          figure.
        </p>
        <p className="example-foot">It's part of the locked holdout, so it's scored once, at the 04:00 freeze.</p>
      </div>
    );
  }
  return (
    <div className="example-card">
      <div className="example-top">
        <span className="example-title">Worked example</span>
        <Pill tone="accent">{fmtMonth(latest.month)}</Pill>
      </div>
      <p className="hero-figure">{fmtPct(latest.national.error_pct)}</p>
      <p className="example-label">Nowcast error for {fmtMonth(latest.month)}, areas 1–13</p>
      <dl className="example-rows">
        <div>
          <dt>Our nowcast</dt>
          <dd>{fmtTonnes(latest.national.pred_kg)}</dd>
        </div>
        <div>
          <dt>Published figure</dt>
          <dd>{fmtTonnes(latest.national.actual_kg)}</dd>
        </div>
        <div>
          <dt>Called on</dt>
          <dd>{fmtDate(latest.made_on)}</dd>
        </div>
      </dl>
      <p className="example-foot">
        Made with only the data public on that day, then checked against the Directorate's release.
      </p>
    </div>
  );
}

// ---- Scale band ----

function tileValue(status: Status<unknown>, value: number | null, due: string): { value: ReactNode; pill?: ReactNode } {
  if (status.state === 'loading') return { value: DASH };
  if (status.state !== 'ok' || value === null) return { value: DASH, pill: <LaterPill>Arrives {due}</LaterPill> };
  return { value: <CountUp value={value} format={fmtCompact} /> };
}

export function ScaleBand({ files }: { files: AllFiles }) {
  const { farms, farmWeeksIndex, price } = files.data;
  const farmList = farms.state === 'ok' ? farms.data : null;
  const years = farmWeeksIndex.state === 'ok' ? [...farmWeeksIndex.data.years].sort((a, b) => a - b) : null;
  const history = price.state === 'ok' ? price.data.history : null;

  const tiles = [
    {
      label: 'Farms tracked',
      ...tileValue(farms, farmList ? farmList.length : null, '21:30'),
      note: 'Every site in the register',
    },
    {
      label: 'Production areas',
      ...tileValue(farms, farmList ? new Set(farmList.map((f) => f.area)).size : null, '21:30'),
      note: 'Along the coast, south to north',
    },
    {
      label: 'Years of weekly farm data',
      ...tileValue(farmWeeksIndex, years ? years.length : null, '21:30'),
      note: years?.length ? `${years[0]} to ${years[years.length - 1]}` : 'Lice, treatments, temperature',
    },
    {
      label: 'Weeks of export prices',
      ...tileValue(price, history ? history.length : null, '03:00'),
      note: history?.length ? `${history[0]!.week} to ${history[history.length - 1]!.week}` : 'Fresh salmon, NOK per kg',
    },
  ];

  return (
    <section className="band band-paper" aria-labelledby="scale-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="scale-title">Built on every farm, every week.</h2>
            <p className="lede">The public record behind every forecast on this page.</p>
          </div>
        </Reveal>
        <div className="tiles">
          {tiles.map((t) => (
            <StatTile key={t.label} label={t.label} value={t.value} note={t.note} pill={t.pill} tone="salmon" />
          ))}
        </div>
      </div>
    </section>
  );
}

// ---- Results band ----

// Plain names for the contract's driver and outcome codes (raw codes stay in the tables).
const DRIVER_NAMES: Record<string, string> = {
  mobile_lice: 'Mobile lice',
  mobile_anom: 'Mobile lice',
  treat_rate: 'Treatments',
  treat_anom: 'Treatments',
  dd_below14: 'Degree-days under 14 °C',
  dd_below8: 'Degree-days under 8 °C',
  dd_8to14: 'Degree-days 8–14 °C',
  dd_above14: 'Degree-days over 14 °C',
};
const OUTCOME_NAMES: Record<string, string> = { log_count: 'fish count', log_avg_kg: 'average weight', log_kg: 'volume' };
const driverName = (d: string) => DRIVER_NAMES[d] ?? d.replace(/_/g, ' ');
const outcomeName = (o: string) => OUTCOME_NAMES[o] ?? o.replace(/^log_/, '').replace(/_/g, ' ');

const ratioLabel = (pct: number, baseline: string) =>
  pct >= 0 ? `lower error than ${baseline}` : `higher error than ${baseline}`;

export function ResultsBand({ files }: { files: AllFiles }) {
  const { nowcast, price, channels } = files.data;
  const f1 = nowcast.state === 'ok' ? nowcast.data.f1 : null;
  const f2 = price.state === 'ok' ? price.data.f2 : null;
  const panel = channels.state === 'ok' ? channels.data.panel : null;
  const holdout = nowcast.state === 'ok' ? nowcast.data.windows.holdout : null;
  const priceHoldout = price.state === 'ok' ? price.data.windows.holdout : null;
  const f2Pct =
    f2 && f2.mae_c0 !== null && f2.mae_c1 !== null && f2.mae_c0 !== 0 ? (1 - f2.mae_c1 / f2.mae_c0) * 100 : null;
  const scoredPanel = (panel ?? []).filter((r) => r.pass !== null);

  return (
    <section className="band band-cream" id="results" aria-labelledby="results-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="results-title">The results.</h2>
            <p className="lede">
              Each test was written down before any model ran, then scored once on a holdout the models never saw.
            </p>
          </div>
        </Reveal>
        <div className="results-grid">
          <StatTile
            className="result-tile"
            tone="salmon"
            label="Harvest nowcast · test F1"
            value={f1 && f1.improvement_pct !== null ? `${Math.abs(f1.improvement_pct).toFixed(1)}%` : 'Pending'}
            note={
              f1 && f1.improvement_pct !== null
                ? `${ratioLabel(f1.improvement_pct, 'baseline B1')}${holdout ? `, holdout ${holdout[0]} to ${holdout[1]}` : ''}`
                : 'Drivers model against baseline B1. Scored once at the 04:00 freeze.'
            }
            pill={f1 ? <PassPill pass={f1.pass} /> : <LaterPill>Scored at 04:00</LaterPill>}
          />
          <StatTile
            className="result-tile"
            tone="butter"
            label="Price forecast · test F2"
            value={f2Pct !== null ? `${Math.abs(f2Pct).toFixed(1)}%` : 'Pending'}
            note={
              f2Pct !== null
                ? `${ratioLabel(f2Pct, 'model c0')} at 4 weeks ahead${priceHoldout ? `, ${priceHoldout[0]} to ${priceHoldout[1]}` : ''}`
                : 'Drivers added to the price model, 4 weeks ahead. Scored once at the 04:00 freeze.'
            }
            pill={f2 ? <PassPill pass={f2.pass} /> : <LaterPill>Scored at 04:00</LaterPill>}
          />
          <div className="result-tile tone-sky">
            <p className="stat-label">How drivers move production · M1 and M2</p>
            {scoredPanel.length ? (
              <ul className="result-list">
                {scoredPanel.map((r, i) => (
                  <li key={`${r.test}-${r.outcome}-${r.driver}-${i}`}>
                    <span>
                      {r.test} · {driverName(r.driver)} → {outcomeName(r.outcome)}
                    </span>
                    <PassPill pass={r.pass === true} />
                  </li>
                ))}
              </ul>
            ) : (
              <>
                <p className="stat-value">Pending</p>
                <p className="stat-note">Lice signature and growth tests. Scored at the 04:00 freeze.</p>
                <div className="stat-pill">
                  <LaterPill>Scored at 04:00</LaterPill>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

// ---- Explore grid ----

type CardState = 'loading' | 'ready' | 'partial' | 'later';

function cardState(parts: Status<unknown>[], complete = true): CardState {
  if (parts.some((s) => s.state === 'loading')) return 'loading';
  const ok = parts.filter((s) => s.state === 'ok').length;
  if (ok === parts.length && complete) return 'ready';
  return ok > 0 ? 'partial' : 'later';
}

export function ExploreGrid({ files }: { files: AllFiles }) {
  const { data, charts } = files;
  const nc = data.nowcast;
  const pr = data.price;
  const ch = data.channels;
  const panelStatus: Status<unknown> =
    ch.state === 'ok' ? (ch.data.panel ? ch : { state: 'missing', url: ch.url }) : ch;
  const hasCurrent =
    (nc.state === 'ok' && nc.data.current != null) || (pr.state === 'ok' && pr.data.current != null);

  const cards: { n: number; id: string; title: string; text: string; state: CardState; due: string }[] = [
    { n: 1, id: 'farms', title: 'Every farm, every week', text: 'Lice, treatments, disease and sea temperature at each farm, week by week.', state: cardState([data.farms, data.farmWeeksIndex]), due: '21:30' },
    { n: 2, id: 'trap', title: 'The seasonality trap', text: "Why raw correlations with price fool you, and what's left once season and trend are gone.", state: cardState([data.trap, charts.trap]), due: '23:30' },
    { n: 3, id: 'split', title: 'More fish, or bigger fish?', text: 'Splitting the harvest into fish count × average weight tells growth from forced early harvests.', state: cardState([ch, charts.channels_bins]), due: '01:30' },
    { n: 4, id: 'nowcast', title: 'The harvest nowcast', text: "Each month's harvest by area, called on the 10th, before the official figure lands.", state: cardState([nc, charts.nowcast_backtest], nc.state === 'ok' && nc.data.f1 !== null), due: '01:30' },
    { n: 5, id: 'drivers', title: 'What drives it', text: 'How much worse the nowcast gets without each group of drivers.', state: cardState([data.drivers, charts.drivers_importance]), due: '04:00' },
    { n: 6, id: 'mechanisms', title: 'Mechanism tests', text: 'Do lice bring harvests forward? Does warmer water grow heavier fish?', state: cardState([panelStatus, charts.channels_panel]), due: '04:00' },
    { n: 7, id: 'price', title: 'The price forecast', text: 'The weekly export price, weeks ahead, against a random walk.', state: cardState([pr, charts.price_scorecard, charts.price_by_year, charts.price_backtest], pr.state === 'ok' && pr.data.f2 !== null), due: '03:00' },
    { n: 8, id: 'current', title: 'Right now', text: "Forecasts from today's data. They can't be checked until after the event.", state: hasCurrent ? 'ready' : 'later', due: 'optional' },
  ];

  return (
    <section className="band band-paper" id="explore" aria-labelledby="explore-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="explore-title">Explore the findings.</h2>
            <p className="lede">Eight findings, each from its own published file. They light up as they land.</p>
          </div>
        </Reveal>
        <div className="explore-grid">
          {cards.map((c) => (
            <a key={c.id} className="explore-card" href={`#${c.id}`} onClick={(e) => goTo(e, c.id)}>
              <span className="eyebrow-number" aria-hidden="true">
                {c.n}
              </span>
              <h3>{c.title}</h3>
              <p>{c.text}</p>
              <span className="explore-foot">
                {c.state === 'ready' ? (
                  <ReadyPill />
                ) : c.state === 'partial' ? (
                  <PartialPill />
                ) : c.state === 'later' ? (
                  <LaterPill>{c.due === 'optional' ? 'Optional' : `Arrives ${c.due}`}</LaterPill>
                ) : (
                  <span className="loading">Loading…</span>
                )}
                <span className="explore-arrow" aria-hidden="true">
                  <IconArrow size={18} />
                </span>
              </span>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

// ---- Pre-registration band ----

export function PreregBand() {
  return (
    <section className="band band-salmon prereg" id="prereg" aria-labelledby="prereg-title">
      <div className="container">
        <Reveal>
          <h2 id="prereg-title">Rules first. Results second.</h2>
          <p className="lede">
            Every pass mark was committed to GitHub before any model saw real outcomes. The holdout was scored once,
            at the 04:00 freeze, and the results don't change after that.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href={`${REPO}/blob/main/prereg/PASS_MARKS.md`} target="_blank" rel="noopener noreferrer">
              Read the pass marks <IconArrow size={18} />
            </a>
            <a className="btn btn-light" href={REPO} target="_blank" rel="noopener noreferrer">
              See the code
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

