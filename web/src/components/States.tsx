import type { ReactNode } from 'react';
import type { Status } from '../data/load';

/** The "coming later" state: a file, or one part of a file, isn't there yet. */
export function Later({ title = 'Coming later', children }: { title?: string; children?: ReactNode }) {
  return (
    <div className="later" role="status">
      <p className="later-title">{title}</p>
      {children}
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
      return (
        <p className="loading" role="status">
          Loading {file}…
        </p>
      );
    case 'ok':
      return <>{children(status.data)}</>;
    case 'missing':
      return (
        <Later>
          <p>
            <code>{file}</code> isn't there yet.
            {due ? ` Due ${due}` : ''}
            {owner ? ` from ${owner}.` : due ? '.' : ''}
          </p>
        </Later>
      );
    case 'invalid':
      return (
        <Later>
          <p>
            <code>{file}</code> is there but doesn't match the agreed format (00-shared.md), so it isn't
            shown.{owner ? ` Tell ${owner}:` : ''}
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
        <Later>
          <p>
            Couldn't load <code>{file}</code> ({status.message}). Reload the page to try again.
          </p>
        </Later>
      );
  }
}

/** One-word status for the file table. Text and symbol, never colour alone. */
export function statusText(status: Status<unknown>): { symbol: string; text: string; tone: string } {
  switch (status.state) {
    case 'loading':
      return { symbol: '…', text: 'Loading', tone: 'muted' };
    case 'ok':
      return { symbol: '✓', text: 'Loaded', tone: 'ok' };
    case 'missing':
      return { symbol: '○', text: 'Not there yet', tone: 'muted' };
    case 'invalid':
      return { symbol: '✕', text: "Doesn't match the format", tone: 'bad' };
    case 'error':
      return { symbol: '!', text: "Couldn't load", tone: 'bad' };
  }
}
