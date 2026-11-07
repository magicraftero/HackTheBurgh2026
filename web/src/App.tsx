import { useRef, useState } from 'react';
import {
  SCENARIOS,
  SCENARIO_LABELS,
  clearCache,
  currentSource,
  useAllFiles,
  type Source,
} from './data/source';
import { FishingIntro, Hook } from './intro/FishingIntro';
import { SitePage } from './page/SitePage';

export function App() {
  const [source] = useState<Source>(currentSource);
  const [generation, setGeneration] = useState(0);
  const files = useAllFiles(source, generation);
  const siteRef = useRef<HTMLDivElement>(null);

  const checkAgain = () => {
    clearCache();
    setGeneration((g) => g + 1);
  };

  return (
    <>
      <FishingIntro siteRef={siteRef} />
      <div ref={siteRef} className="site-wrap">
        <Hook />
        <div className="site">
          {import.meta.env.DEV ? <DevBar source={source} /> : null}
          <SitePage files={files} source={source} generation={generation} onCheckAgain={checkAgain} />
        </div>
      </div>
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
