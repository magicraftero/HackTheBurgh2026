// The map's projection, shared by the site and scripts/make-basemap.ts so the
// coastline file and the farm dots always line up.
//
// A spherical transverse Mercator centred on 15°E, the same central meridian
// as UTM zone 33, which Norway's own maps use. Units are kilometres; x grows
// east and y grows south (SVG's direction), with the origin at 15°E, 64°N.

export const PROJECTION = { type: 'transverse-mercator', lon0: 15, lat0: 64, radiusKm: 6371.0088 } as const;

export type Point = [number, number];
export type Rect = { x: number; y: number; w: number; h: number };

const RAD = Math.PI / 180;

export function project(lon: number, lat: number): Point {
  const lambda = (lon - PROJECTION.lon0) * RAD;
  const phi = lat * RAD;
  const b = Math.cos(phi) * Math.sin(lambda);
  const x = PROJECTION.radiusKm * Math.atanh(b);
  const y = PROJECTION.radiusKm * (Math.atan2(Math.tan(phi), Math.cos(lambda)) - PROJECTION.lat0 * RAD);
  return [x, -y];
}

/**
 * The whole-coast view, in projected kilometres: mainland Norway from Lindesnes
 * to the Russian border with a margin of sea. scripts/make-basemap.ts clips
 * the coastline to (a little more than) this.
 */
export const VIEW: Rect = { x: -640, y: -905, w: 1330, h: 1610 };

/** Scale and offset that fit `view` inside a box of `width` × `height` pixels, centred. */
export function fit(view: Rect, width: number, height: number) {
  const k = Math.min(width / view.w, height / view.h);
  return { k, tx: (width - view.w * k) / 2 - view.x * k, ty: (height - view.h * k) / 2 - view.y * k };
}

export function padRect(r: Rect, pad: number): Rect {
  return { x: r.x - pad, y: r.y - pad, w: r.w + 2 * pad, h: r.h + 2 * pad };
}

/** The smallest rectangle around the points (all of them projected already). */
export function bounds(points: Point[]): Rect {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const [x, y] of points) {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

/** Linear blend between two rectangles, for animated zooms. */
export function lerpRect(a: Rect, b: Rect, t: number): Rect {
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, w: a.w + (b.w - a.w) * t, h: a.h + (b.h - a.h) * t };
}
