import type { ReactNode } from 'react';
import { CountUp, LaterPill, PassPill, Pill, Reveal, StatTile } from '../components/Bits';
import { DASH, fmtCompact, fmtDate, fmtMonth, fmtPct, fmtTonnes } from '../components/format';
import { IconArrow } from '../components/Icons';
import { finalLatest, finalScore } from '../data/finalModel';
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
          <h2 id="top-heading" className="display" tabIndex={-1}>
            The harvest, called early.
          </h2>
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
          <WorkedExampleCard status={files.data.combined} />
        </Reveal>
      </div>
    </section>
  );
}

function WorkedExampleCard({ status }: { status: AllFiles['data']['combined'] }) {
  const latest = status.state === 'ok' ? finalLatest(status.data) : null;
  if (!latest) {
    return (
      <div className="example-card">
        <div className="example-top">
          <span className="example-title">Worked example</span>
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
        <span className="example-title">Worked example</span>
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

// ---- Scale band ----

function tileValue(status: Status<unknown>, value: number | null): { value: ReactNode; pill?: ReactNode } {
  if (status.state === 'loading') return { value: DASH };
  if (status.state !== 'ok' || value === null) return { value: DASH, pill: <LaterPill>Coming soon</LaterPill> };
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
      label: 'Weeks of export prices',
      ...tileValue(price, history ? history.length : null),
      note: history?.length ? `${history[0]!.week.slice(0, 4)} to ${history[history.length - 1]!.week.slice(0, 4)}` : 'Fresh salmon, NOK per kg',
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
  const { combined, price, channels, nowcast } = files.data;
  const f1 = nowcast.state === 'ok' ? nowcast.data.f1 : null;
  const final = combined.state === 'ok' ? finalScore(combined.data, 'log_kg') : null;
  const finalMonths = combined.state === 'ok' ? combined.data.windows.holdout : null;
  const f2 = price.state === 'ok' ? price.data.f2 : null;
  const panel = channels.state === 'ok' ? channels.data.panel : null;
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
              Our harvest forecast on months it never trained on, and the tests we set ourselves in advance, including the
              ones we failed.
            </p>
          </div>
        </Reveal>
        <div className="results-grid">
          <StatTile
            className="result-tile"
            tone="salmon"
            label="Harvest forecast"
            value={final ? `${Math.round(final.accuracyPct)}%` : 'Pending'}
            note={
              final && finalMonths
                ? `accurate on tonnes per area, ${fmtMonth(finalMonths[0])} to ${fmtMonth(finalMonths[1])}. That's ${Math.round(final.lessErrorPct)}% less error than our baseline model.`
                : 'Tested on months it never trained on.'
            }
            pill={final ? undefined : <LaterPill>Coming soon</LaterPill>}
          />
          <StatTile
            className="result-tile"
            tone="butter"
            label="Price forecast · test F2"
            value={f2Pct !== null ? `${Math.abs(f2Pct).toFixed(1)}%` : 'Pending'}
            note={
              f2Pct !== null
                ? `${ratioLabel(f2Pct, 'model c0')} at 4 weeks ahead${priceHoldout ? `, ${priceHoldout[0]} to ${priceHoldout[1]}` : ''}`
                : 'Whether farm data improves the four-week price forecast.'
            }
            pill={f2 ? <PassPill pass={f2.pass} /> : <LaterPill>Coming soon</LaterPill>}
          />
          <div className="result-tile tone-sky">
            <p className="stat-label">The tests we set in advance</p>
            {f1 || scoredPanel.length ? (
              <ul className="result-list">
                {f1 ? (
                  <li>
                    <span>F1 · Farm data cuts forecast error by 5%</span>
                    <PassPill pass={f1.pass === true} />
                  </li>
                ) : null}
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
                <p className="stat-note">How lice and warmth change the harvest.</p>
                <div className="stat-pill">
                  <LaterPill>Coming soon</LaterPill>
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

type CardState = 'loading' | 'ready' | 'later';

function cardState(parts: Status<unknown>[]): CardState {
  if (parts.some((s) => s.state === 'loading')) return 'loading';
  return parts.some((s) => s.state === 'ok') ? 'ready' : 'later';
}

export function ExploreGrid({ files }: { files: AllFiles }) {
  const { data } = files;
  const ch = data.channels;
  const panelStatus: Status<unknown> =
    ch.state === 'ok' ? (ch.data.panel ? ch : { state: 'missing', url: ch.url }) : ch;

  const cards: { n: number; id: string; title: string; text: string; state: CardState }[] = [
    { n: 1, id: 'farms', title: 'Every farm, every week', text: 'Lice, treatments, disease and sea temperature at each farm, week by week.', state: cardState([data.farms, data.farmWeeksIndex]) },
    { n: 2, id: 'trap', title: 'The seasonality trap', text: "Why raw correlations with price fool you, and what's left once season and trend are gone.", state: cardState([data.trap]) },
    { n: 3, id: 'split', title: 'More fish, or bigger fish?', text: 'Splitting the harvest into fish count × average weight tells growth from forced early harvests.', state: cardState([ch]) },
    { n: 4, id: 'nowcast', title: 'The harvest forecast', text: "Each month's harvest by area, called on the 10th, before the official figure lands.", state: cardState([data.combined]) },
    { n: 5, id: 'drivers', title: 'What drives it', text: 'How much worse the forecast gets without each group of factors.', state: cardState([data.drivers]) },
    { n: 6, id: 'mechanisms', title: 'How the biology acts', text: 'Do lice bring harvests forward? Does warmer water grow heavier fish?', state: cardState([panelStatus]) },
    { n: 7, id: 'price', title: 'The price forecast', text: 'The weekly export price, weeks ahead, against a random walk.', state: cardState([data.price]) },
    { n: 8, id: 'current', title: 'Right now', text: 'Our forecast for the latest month, before the official figure is out.', state: cardState([data.farmerActions]) },
  ];

  return (
    <section className="band band-paper" id="explore" aria-labelledby="explore-title">
      <div className="container">
        <Reveal className="section-head">
          <div>
            <h2 id="explore-title">Explore the findings.</h2>
            <p className="lede">Eight findings from Norway's public salmon data.</p>
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
                {c.state === 'later' ? <LaterPill>Coming soon</LaterPill> : <span />}
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
    <section className="band band-coral prereg" id="prereg" aria-labelledby="prereg-title">
      <div className="container">
        <Reveal>
          <h2 id="prereg-title">Rules first. Results second.</h2>
          <p className="lede">
            We committed every pass mark to GitHub before any model saw real outcomes, and we report the tests we failed
            next to the ones we passed. We opened the held-back months a few hours ahead of plan, at 23:47 on 7 November,
            and our harvest forecast was designed after our first model missed its mark, using only earlier data.
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

