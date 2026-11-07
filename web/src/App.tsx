import { useState } from 'react';
import {
  SCENARIOS,
  SCENARIO_LABELS,
  clearCache,
  currentSource,
  useAllFiles,
  type Source,
} from './data/source';
import { FindingsPage } from './page/FindingsPage';

export function App() {
  const [source] = useState<Source>(currentSource);
  const [generation, setGeneration] = useState(0);
  const files = useAllFiles(source, generation);

  const checkAgain = () => {
    clearCache();
    setGeneration((g) => g + 1);
  };

  return (
    <>
      {import.meta.env.DEV ? <DevBar source={source} /> : null}
      <header className="site-header">
        {source.kind === 'mock' ? (
          <p className="mock-banner" role="note">
            <strong>Mock data.</strong> These are made-up numbers for building the site, not findings.
          </p>
        ) : null}
        <h1>Norwegian salmon: production and price</h1>
        <p className="lede">
          Test page: every finding, the files behind it, and whether they've arrived. This isn't the final
          design.
        </p>
        <button type="button" onClick={checkAgain}>
          Check for new files
        </button>
      </header>
      <main className="page">
        {/* A new key on "Check for new files" also reloads the farm year files. */}
        <FindingsPage key={generation} files={files} source={source} />
      </main>
    </>
  );
}

/** Development only (never in production builds): switch between real and mock files. */
function DevBar({ source }: { source: Source }) {
  const current = source.kind === 'real' ? 'real' : source.scenario;
  return (
    <nav className="devbar" aria-label="Development data switch">
      <span>Dev only. Data:</span>
      <a href="?" aria-current={current === 'real' ? 'page' : undefined}>
        Real files
      </a>
      {SCENARIOS.map((s) => (
        <a key={s} href={`?mock=${s}`} aria-current={current === s ? 'page' : undefined}>
          {SCENARIO_LABELS[s]}
        </a>
      ))}
    </nav>
  );
}
