import type { MouseEvent, RefObject } from 'react';
import { Pill } from '../components/Bits';
import { HookMark, IconClose, IconRefresh } from '../components/Icons';
import { StatusCell } from '../components/States';
import { CHART_NAMES, CHARTS, DATA_FILES, DATA_KEYS, chartPath } from '../data/files';
import type { Status } from '../data/load';
import type { AllFiles, Source } from '../data/source';
import { REPLAY_EVENT } from '../intro/FishingIntro';

export const REPO = 'https://github.com/magicraftero/HackTheBurgh2026';

/** Smooth-scroll to a section instead of jumping (instant for reduced motion). */
export function goTo(e: MouseEvent<HTMLElement>, id: string) {
  const el = document.getElementById(id);
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
  ['nowcast', 'Production'],
  ['price', 'Price'],
  ['farms', 'Farms'],
  ['results', 'Tests'],
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
        <a className="btn btn-primary btn-sm" href="#top" onClick={(e) => goTo(e, 'top')}>
          See the forecast
        </a>
      </nav>
    </header>
  );
}

// ---- Notice at the top of the site ----

export function Notice({ files, source }: { files: AllFiles; source: Source }) {
  const { nowcast, price } = files.data;
  const scored = (nowcast.state === 'ok' && nowcast.data.f1 !== null) || (price.state === 'ok' && price.data.f2 !== null);
  return (
    <div className="notice">
      <span className="notice-pill">
        {source.kind === 'mock' ? <Pill tone="mock">Mock data: made-up numbers, not findings</Pill> : null}
        {scored ? (
          <span>
            The holdout results are in.{' '}
            <a href="#results" onClick={(e) => goTo(e, 'results')}>
              See how the forecasts did
            </a>
          </span>
        ) : (
          <span>
            Holdout results land at the 04:00 analysis freeze.{' '}
            <a href="#prereg" onClick={(e) => goTo(e, 'prereg')}>
              How we test
            </a>
          </span>
        )}
      </span>
    </div>
  );
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
  const backToBoat = () => window.dispatchEvent(new Event(REPLAY_EVENT));
  return (
    <footer className="footer">
      <div className="container">
        <div className="footer-grid">
          <div>
            <span className="brand">
              <HookMark size={22} /> Salmon Signal
            </span>
            <p className="footer-about">
              Made in 24 hours at HackTheBurgh XIII, Edinburgh, by The Edinburgers. Forecasting Norway's salmon
              harvest and price from public data.
            </p>
          </div>
          <div>
            <h3>The data</h3>
            <ul>
              <li>
                <a href="https://www.fiskeridir.no" target="_blank" rel="noopener noreferrer">
                  Directorate of Fisheries
                </a>
              </li>
              <li>
                <a href="https://www.barentswatch.no" target="_blank" rel="noopener noreferrer">
                  BarentsWatch
                </a>
              </li>
              <li>
                <a href="https://www.ssb.no" target="_blank" rel="noopener noreferrer">
                  Statistics Norway
                </a>
              </li>
              <li>
                <a href="https://www.norges-bank.no" target="_blank" rel="noopener noreferrer">
                  Norges Bank
                </a>
              </li>
              <li>
                <a href="https://www.naturalearthdata.com" target="_blank" rel="noopener noreferrer">
                  Natural Earth
                </a>{' '}
                (the coastline)
              </li>
            </ul>
          </div>
          <div>
            <h3>The project</h3>
            <ul>
              <li>
                <a href={REPO} target="_blank" rel="noopener noreferrer">
                  Code on GitHub
                </a>
              </li>
              <li>
                <a href={`${REPO}/blob/main/prereg/PASS_MARKS.md`} target="_blank" rel="noopener noreferrer">
                  The pass marks
                </a>
              </li>
              <li>
                <a href={`${REPO}/tree/main/docs/plans`} target="_blank" rel="noopener noreferrer">
                  How it was built
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h3>This site</h3>
            <ul>
              <li>
                <button type="button" className="link" onClick={onOpenStatus}>
                  Data status ({loaded}/{rows.length} files)
                </button>
              </li>
              <li>
                <button type="button" className="link" onClick={backToBoat}>
                  Back to the fisherman
                </button>
              </li>
              <li>
                <a href="#top" onClick={(e) => goTo(e, 'top')}>
                  Back to top
                </a>
              </li>
            </ul>
          </div>
        </div>
        <p className="footer-small">
          Every number on this page is read from the project's published files; none is typed in by hand.
          Research, not investment advice.
        </p>
      </div>
    </footer>
  );
}
