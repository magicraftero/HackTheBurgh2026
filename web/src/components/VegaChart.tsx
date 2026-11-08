import { useEffect, useRef, useState } from 'react';
import type { VisualizationSpec } from 'vega-embed';
import type { ChartSpec } from '../data/schemas';

type Props = {
  spec: ChartSpec;
  /** What the chart shows, for screen readers. */
  label: string;
};

/**
 * Draws any Vega-Lite spec from web/public/charts/ with vega-embed.
 *
 * - Specs with width "container" fill the column and follow window resizes.
 * - Fixed-width specs (concat and facet charts) shrink to fit narrow screens.
 * - The chart library loads on first use, so the rest of the page shows fast.
 * - A spec that can't be drawn shows a message instead of breaking the page.
 */
export function VegaChart({ spec, label }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Each run draws into its own host, so a slow, outdated draw can't leave
    // a second chart behind.
    const host = document.createElement('div');
    host.className = 'chart-host';
    el.appendChild(host);
    let live = true;
    let finalize: (() => void) | undefined;
    setProblem(null);

    import('vega-embed')
      .then(({ default: embed }) => {
        if (!live) return null;
        const copy = structuredClone(spec) as VisualizationSpec;
        return embed(host, copy, { actions: false, renderer: 'svg' });
      })
      .then((result) => {
        if (!result) return;
        if (live) finalize = () => result.finalize();
        else result.finalize();
      })
      .catch((e: unknown) => {
        if (live) setProblem(e instanceof Error ? e.message : String(e));
      });

    return () => {
      live = false;
      finalize?.();
      host.remove();
    };
  }, [spec]);

  return (
    <figure className="chart" aria-label={label}>
      {problem ? (
        <p className="chart-problem" role="status">
          This chart couldn't be drawn: {problem}
        </p>
      ) : null}
      <div ref={ref} className="chart-canvas" />
    </figure>
  );
}
