import { useEffect, useState } from 'react';
import type { z } from 'zod';
import {
  CHART_NAMES,
  DATA_FILES,
  DATA_KEYS,
  chartPath,
  farmWeeksYearPath,
  type ChartName,
  type DataKey,
  type DataOf,
} from './files';
import { loadJson, type Loaded, type Status } from './load';
import { ChartSpecSchema, FarmWeeksYearSchema, type ChartSpec, type FarmWeeksYear } from './schemas';

// ---- Where the data comes from ----

export const SCENARIOS = ['pre', 'post', 'none'] as const;
export type Scenario = (typeof SCENARIOS)[number];
export type Source = { kind: 'real' } | { kind: 'mock'; scenario: Scenario };

export const SCENARIO_LABELS: Record<Scenario, string> = {
  pre: 'Mock data: before the 04:00 freeze',
  post: 'Mock data: after the 04:00 freeze',
  none: 'Mock data: no files yet',
};

/**
 * Development only: `?mock=pre`, `?mock=post` or `?mock=none` switches to the
 * mock files in public/data/_mock/. Production builds always read the real
 * files: import.meta.env.DEV is false there, so this code is removed.
 */
export function currentSource(): Source {
  if (!import.meta.env.DEV || typeof location === 'undefined') return { kind: 'real' };
  const wanted = new URLSearchParams(location.search).get('mock');
  const scenario = SCENARIOS.find((s) => s === wanted);
  return scenario ? { kind: 'mock', scenario } : { kind: 'real' };
}

export const sourceKey = (s: Source) => (s.kind === 'real' ? 'real' : `mock-${s.scenario}`);

/** Turn a contract path (data/x.json, charts/x.vl.json) into a URL. */
export function resolveUrl(path: string, source: Source): string {
  // BASE_URL is "./" in builds, so URLs are relative to the page, never "/".
  const base = import.meta.env.BASE_URL;
  // Production builds read the real files, whatever `source` says.
  if (source.kind === 'real' || !import.meta.env.DEV) return base + path;
  const rest = path.startsWith('data/') ? path.slice('data/'.length) : path;
  return `${base}data/_mock/${source.scenario}/${rest}`;
}

// ---- Loading, with one request per file however many sections use it ----

const cache = new Map<string, Promise<Loaded<unknown>>>();

function cachedLoad<T>(url: string, schema: z.ZodType<T>): Promise<Loaded<T>> {
  let p = cache.get(url) as Promise<Loaded<T>> | undefined;
  if (!p) {
    p = loadJson(url, schema).then((r) => {
      if (r.state === 'error') cache.delete(url); // let the next try fetch again
      return r;
    });
    cache.set(url, p);
  }
  return p;
}

/** Forget every loaded file, so the next load fetches fresh copies. */
export const clearCache = () => cache.clear();

export const loadData = <K extends DataKey>(key: K, source: Source) =>
  cachedLoad(
    resolveUrl(DATA_FILES[key].path, source),
    DATA_FILES[key].schema as unknown as z.ZodType<DataOf<K>>,
  );

export const loadChart = (name: ChartName, source: Source) =>
  cachedLoad(resolveUrl(chartPath(name), source), ChartSpecSchema);

export const loadFarmWeeksYear = (year: number, source: Source) =>
  cachedLoad(resolveUrl(farmWeeksYearPath(year), source), FarmWeeksYearSchema);

// ---- React hooks ----

export type AllFiles = {
  data: { [K in DataKey]: Status<DataOf<K>> };
  charts: Record<ChartName, Status<ChartSpec>>;
};

export function emptyFiles(): AllFiles {
  const loading = { state: 'loading' } as const;
  return {
    data: Object.fromEntries(DATA_KEYS.map((k) => [k, loading])) as AllFiles['data'],
    charts: Object.fromEntries(CHART_NAMES.map((c) => [c, loading])) as AllFiles['charts'],
  };
}

/** Load every findings file and chart in parallel; each fills in as it lands. */
export function useAllFiles(source: Source, generation: number): AllFiles {
  const [files, setFiles] = useState<AllFiles>(emptyFiles);
  const key = sourceKey(source);

  useEffect(() => {
    let live = true;
    setFiles(emptyFiles());
    for (const k of DATA_KEYS) {
      void loadData(k, source).then((r) => {
        if (live) setFiles((f) => ({ ...f, data: { ...f.data, [k]: r } as AllFiles['data'] }));
      });
    }
    for (const c of CHART_NAMES) {
      void loadChart(c, source).then((r) => {
        if (live) setFiles((f) => ({ ...f, charts: { ...f.charts, [c]: r } }));
      });
    }
    return () => {
      live = false;
    };
    // `source` is fully described by `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, generation]);

  return files;
}

/** One farm-weeks year file, loaded only when it's asked for. */
export function useFarmWeeksYear(year: number | null, source: Source): Status<FarmWeeksYear> | null {
  const [status, setStatus] = useState<Status<FarmWeeksYear> | null>(null);
  const key = sourceKey(source);

  useEffect(() => {
    if (year === null) {
      setStatus(null);
      return;
    }
    let live = true;
    setStatus({ state: 'loading' });
    void loadFarmWeeksYear(year, source).then((r) => {
      if (live) setStatus(r);
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, key]);

  return status;
}
