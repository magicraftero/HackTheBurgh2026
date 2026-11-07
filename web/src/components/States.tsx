import type { ReactNode } from 'react';
import type { Status } from '../data/load';
import { IconAlert, IconCheck, IconClock } from './Icons';

/** The "coming later" state: a file, or one part of a file, isn't there yet. */
export function Later({ title = 'Coming later', children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="later">
      <span className="later-icon">
        <IconClock size={20} />
      </span>
      <div className="later-text">
        <p className="later-title">{title}</p>
        {children}
      </div>
    </div>
  );
}

type ViewProps<T> = {
  status: Status<T>;
  /** The file's name, as people will say it ("nowcast.json"). */
  file: string;
  owner?: string;
  due?: string;
  children: (data: T) => ReactNode;
};

/** Shows a loaded file's content, or the right "not yet" state. */
export function StatusView<T>({ status, file, owner, due, children }: ViewProps<T>) {
  switch (status.state) {
    case 'loading':
      return <p className="loading">Loading…</p>;
    case 'ok':
      return <>{children(status.data)}</>;
    case 'missing':
      return (
        <Later>
          <p>{due ? `Arrives ${due}.` : 'Not published yet.'}</p>
          <p className="note">
            Waiting for <code>{file}</code>
            {owner ? ` from ${owner}` : ''}.
          </p>
        </Later>
      );
    case 'invalid':
      return (
        <Later title="Held back">
          <p>
            <code>{file}</code> is there but doesn't match the agreed format yet, so it isn't shown.
            {owner ? ` Tell ${owner}:` : ''}
          </p>
          <ul className="problems">
            {status.problems.map((p, i) => (
              <li key={i}>
                <code>{p}</code>
              </li>
            ))}
          </ul>
        </Later>
      );
    case 'error':
      return (
        <Later title="Couldn't load">
          <p>
            <code>{file}</code> didn't load ({status.message}). Reload the page to try again.
          </p>
        </Later>
      );
  }
}

/** Status for the file table: an icon and a word, never colour alone. */
export function StatusCell({ status }: { status: Status<unknown> }) {
  switch (status.state) {
    case 'loading':
      return <span className="status-cell">Loading…</span>;
    case 'ok':
      return (
        <span className="status-cell is-ok">
          <IconCheck size={16} /> Loaded
        </span>
      );
    case 'missing':
      return (
        <span className="status-cell">
          <IconClock size={16} /> Not there yet
        </span>
      );
    case 'invalid':
      return (
        <span className="status-cell is-bad">
          <IconAlert size={16} /> Doesn't match the format
        </span>
      );
    case 'error':
      return (
        <span className="status-cell is-bad">
          <IconAlert size={16} /> Couldn't load
        </span>
      );
  }
}
