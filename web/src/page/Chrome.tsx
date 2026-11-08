import type { MouseEvent, RefObject } from 'react';
import { Pill } from '../components/Bits';
import { HookMark, IconClose, IconRefresh } from '../components/Icons';
import { StatusCell } from '../components/States';
import { fmtMonth, fmtTonnes } from '../components/format';
import { showBuildNotes } from '../data/debug';
import { CHART_NAMES, CHARTS, DATA_FILES, DATA_KEYS, chartPath } from '../data/files';
import type { Status } from '../data/load';
import type { AllFiles, Source } from '../data/source';

/** Smooth-scroll to a section instead of jumping (instant for reduced motion). */
export function goTo(e: MouseEvent<HTMLElement>, id: string) {
  const section = document.getElementById(id);
  // A section can hand over to an element inside it (the farm map lands with
  // the whole map on screen); without that element, the section itself.
  const inner = section?.dataset.scrollTo ? document.getElementById(section.dataset.scrollTo) : null;
  const el = inner ?? section;
  if (!el) return;
  e.preventDefault();
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
  history.replaceState(null, '', id === 'intro' ? location.pathname + location.search : `#${id}`);
}

type FileRow = { file: string; owner: string; due: string; status: Status<unknown> };

export function fileRows(files: AllFiles): FileRow[] {
  return [
    ...DATA_KEYS.map((k) => ({ file: DATA_FILES[k].path, owner: DATA_FILES[k].owner, due: DATA_FILES[k].due, status: files.data[k] })),
    ...CHART_NAMES.map((c) => ({ file: chartPath(c), owner: CHARTS[c].owner, due: CHARTS[c].due, status: files.charts[c] })),
  ];
}

// ---- The floating nav: one pill, fixed over the hero and the site ----

const NAV_LINKS: [string, string][] = [
  ['results', 'Results'],
  ['current', 'Next forecast'],
  ['price', 'Price'],
  ['farms', 'Map'],
  ['nowcast', 'Historic view'],
  ['split', 'Harvest'],
  ['trap', 'Seasonality'],
];

export function FloatNav() {
  return (
    <header className="float-nav">
      <nav aria-label="Main">
        <a className="brand" href="#intro" onClick={(e) => goTo(e, 'intro')}>
          <HookMark size={18} /> Salmon Signal
        </a>
        {NAV_LINKS.map(([id, label]) => (
          <a key={id} className="nav-link" href={`#${id}`} onClick={(e) => goTo(e, id)}>
            {label}
          </a>
        ))}
        <a className="nav-link" href="cockpit/index.html">
          My farm
        </a>
      </nav>
    </header>
  );
}

// ---- Notice at the top of the site ----

export function Notice({ files, source }: { files: AllFiles; source: Source }) {
  const { farmerActions, combined } = files.data;
  const live = farmerActions.state === 'ok' && isUpcoming(farmerActions.data.publishes_around) ? farmerActions.data : null;
  const results = combined.state === 'ok';
  const mock = source.kind === 'mock';
  if (!live && !results && !mock) return null;
  return (
    <div className="notice">
      <span className="notice-pill">
        {mock ? <Pill tone="mock">Mock data: made-up numbers, not findings</Pill> : null}
        {live ? (
          <span>
            Our {fmtMonth(live.target_month)} forecast: {fmtTonnes(live.national.kg)}, ahead of the official figure.{' '}
            <a href="#current" onClick={(e) => goTo(e, 'current')}>
              See it
            </a>
          </span>
        ) : results ? (
          <span>
            Our forecasts against the published figures.{' '}
            <a href="#results" onClick={(e) => goTo(e, 'results')}>
              See the results
            </a>
          </span>
        ) : null}
      </span>
    </div>
  );
}

/** True until the day an official figure is due ("2026-11-20"). */
export function isUpcoming(day: string, now = new Date()): boolean {
  return day >= now.toISOString().slice(0, 10);
}

// ---- Data status dialog ----

type DialogProps = {
  dialogRef: RefObject<HTMLDialogElement | null>;
  files: AllFiles;
  onCheckAgain: () => void;
};

export function DataStatusDialog({ dialogRef, files, onCheckAgain }: DialogProps) {
  const rows = fileRows(files);
  const loaded = rows.filter((r) => r.status.state === 'ok').length;
  return (
    <dialog ref={dialogRef} className="status-dialog" aria-labelledby="status-title">
      <div className="status-head">
        <h2 id="status-title" style={{ fontSize: '1.4rem' }}>
          Data status
        </h2>
        <button type="button" className="icon-btn" aria-label="Close" onClick={() => dialogRef.current?.close()}>
          <IconClose size={18} />
        </button>
      </div>
      <div className="status-body">
        <div className="verdict-row">
          <p>
            <strong>
              {loaded} of {rows.length} files in.
            </strong>{' '}
            Findings land through the night; each part shows as soon as its file does.
          </p>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onCheckAgain}>
            <IconRefresh size={16} /> Check for new files
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Every file the site reads and whether it has arrived</caption>
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">From</th>
                <th scope="col">Due</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.file}>
                  <th scope="row">
                    <code>{r.file}</code>
                  </th>
                  <td>{r.owner}</td>
                  <td>{r.due}</td>
                  <td>
                    <StatusCell status={r.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          The farm year files (<code>data/farm_weeks/&lt;year&gt;.json</code>) load when you pick a year in
          “Every farm, every week”.
        </p>
      </div>
    </dialog>
  );
}

// ---- Footer ----

export function Footer({ files, onOpenStatus }: { files: AllFiles; onOpenStatus: () => void }) {
  const rows = fileRows(files);
  const loaded = rows.filter((r) => r.status.state === 'ok').length;
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <span className="brand">
              <HookMark size={40} /> Salmon Signal
            </span>
            <p className="footer-about">
              Forecasting Norway's salmon harvest and price from public data.
            </p>
          </div>
          <div>
            <h3>The data we used</h3>
            <ul>
              <li>
                <a href="https://www.fiskeridir.no" target="_blank" rel="noopener noreferrer">
                  Directorate of Fisheries
                </a>{' '}
                (fish stocks, harvest, farm register)
              </li>
              <li>
                <a href="https://www.barentswatch.no" target="_blank" rel="noopener noreferrer">
                  BarentsWatch
                </a>{' '}
                (lice, treatments, disease)
              </li>
              <li>
                <a href="https://www.ssb.no" target="_blank" rel="noopener noreferrer">
                  Statistics Norway
                </a>{' '}
                (weekly salmon exports)
              </li>
              <li>
                <a href="https://www.norges-bank.no" target="_blank" rel="noopener noreferrer">
                  Norges Bank
                </a>{' '}
                (exchange rates)
              </li>
              <li>
                <a href="https://salmonprice.com/fishpool/public/priceHistory" target="_blank" rel="noopener noreferrer">
                  SISALMONI
                </a>{' '}
                (the salmon price)
              </li>
              <li>
                <a href="https://www.naturalearthdata.com" target="_blank" rel="noopener noreferrer">
                  Natural Earth
                </a>{' '}
                (the coastline)
              </li>
              {showBuildNotes() ? (
                <li>
                  <button type="button" className="link" onClick={onOpenStatus}>
                    Data status ({loaded}/{rows.length} files)
                  </button>
                </li>
              ) : null}
            </ul>
          </div>
        </div>
        <p className="footer-small">
          Research, not investment advice.
        </p>
      </div>
    </footer>
  );
}
