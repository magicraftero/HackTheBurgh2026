// The map's land, coastline and borders: public/map/norway.json, made by
// scripts/make-basemap.ts from Natural Earth. It's the front end's own file,
// the same in every data scenario, and loaded once.

import { useEffect, useState } from 'react';
import { z } from 'zod';
import { loadJson, type Loaded, type Status } from '../data/load';
import { PROJECTION, VIEW } from './projection';

const pathData = z.string().regex(/^(M[^M]+)*$/, 'not SVG path data');

export const BasemapSchema = z.object({
  about: z.string(),
  projection: z.object({
    type: z.literal(PROJECTION.type),
    lon0: z.literal(PROJECTION.lon0),
    lat0: z.literal(PROJECTION.lat0),
    radiusKm: z.literal(PROJECTION.radiusKm),
  }),
  view: z.tuple([z.literal(VIEW.x), z.literal(VIEW.y), z.literal(VIEW.w), z.literal(VIEW.h)]),
  countries: z.array(z.string()),
  norway: pathData.min(1000),
  neighbours: pathData,
  coast: pathData.min(1000),
  borders: pathData,
});
export type Basemap = z.infer<typeof BasemapSchema>;

export const BASEMAP_URL = 'map/norway.json';

let pending: Promise<Loaded<Basemap>> | null = null;

export function loadBasemap(): Promise<Loaded<Basemap>> {
  if (!pending) {
    pending = loadJson(BASEMAP_URL, BasemapSchema).then((r) => {
      if (r.state !== 'ok') pending = null; // try again next time
      return r;
    });
  }
  return pending;
}

export function useBasemap(): Status<Basemap> {
  const [status, setStatus] = useState<Status<Basemap>>({ state: 'loading' });
  useEffect(() => {
    let live = true;
    void loadBasemap().then((r) => {
      if (live) setStatus(r);
    });
    return () => {
      live = false;
    };
  }, []);
  return status;
}
