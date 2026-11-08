// Builds public/map/norway.json, the land, coastline and borders behind the
// farm map, from Natural Earth's 1:10m countries (public domain) as packaged
// in world-atlas 2.0.2. Run it once; the output is committed, so nobody else
// needs the download.
//
//   npm pack world-atlas@2.0.2 --ignore-scripts && tar -xzf world-atlas-2.0.2.tgz
//   npm run basemap -- /absolute/path/to/package/countries-10m.json
//
// Steps: decode the TopoJSON arcs, project them with src/map/projection.ts,
// simplify each arc a little (shared arcs the same way, so borders still
// meet), rebuild each country's rings, clip them to the view, and write
// compact SVG paths. Coastlines and land borders are separate stroke-only
// paths, so the clip edges are never drawn as coast.

import { PROJECTION, VIEW, bounds, project, type Point, type Rect } from '../src/map/projection';
import type { IO } from './io';

type Ring = number[];
type Geometry = {
  type: string | null;
  id?: string;
  properties?: { name?: string };
  arcs?: Ring[] | Ring[][];
};
type Topology = {
  type: string;
  transform: { scale: [number, number]; translate: [number, number] };
  arcs: [number, number][][];
  objects: { countries: { geometries: Geometry[] } };
};

const OUT = 'public/map/norway.json';
const SIMPLIFY_KM = 0.25; // Douglas–Peucker tolerance; Natural Earth 1:10m is ~0.2 km apart
const MIN_ISLAND_KM2 = 0.4; // drop specks smaller than this
// The view plus a margin: 25 km above and below, 180 km either side, because on
// a short desktop screen the map's column is wider than the map (styles.css,
// --map-w), so a little more land and sea shows left and right.
const CLIP = { x: VIEW.x - 180, y: VIEW.y - 25, w: VIEW.w + 360, h: VIEW.h + 50 };
// Points outside this box are pulled onto its edge before projecting: a transverse
// Mercator blows up 90° from its meridian, and everything out there is clipped
// away anyway. Clamping keeps each ring closed and the part inside unchanged.
// Longitude is measured from the map's meridian first, so Russia's outline,
// which crosses the 180° line, stays continuous and lands on the east edge.
const NEAR = { w: -12, e: 48, s: 50, n: 76 };
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
function nearLon(lon: number): number {
  const fromMeridian = ((((lon - PROJECTION.lon0 + 180) % 360) + 360) % 360) - 180;
  return PROJECTION.lon0 + clamp(fromMeridian, NEAR.w - PROJECTION.lon0, NEAR.e - PROJECTION.lon0);
}

export default async function main(io: IO): Promise<number> {
  const file = io.args[0];
  if (!file) {
    console.error('usage: npm run basemap -- /path/to/world-atlas/package/countries-10m.json');
    return 2;
  }
  const text = io.read(file);
  if (text === null) {
    console.error(`can't read ${file}`);
    return 2;
  }
  const topo = JSON.parse(text) as Topology;
  if (topo.type !== 'Topology' || !topo.objects?.countries) {
    console.error(`${file} isn't a world-atlas countries file`);
    return 2;
  }

  // ---- Arcs: decode, project, simplify ----
  const [sx, sy] = topo.transform.scale;
  const [tx, ty] = topo.transform.translate;
  const lonLat: Point[][] = topo.arcs.map((arc) => {
    let x = 0;
    let y = 0;
    return arc.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * sx + tx, y * sy + ty] as Point;
    });
  });
  const arcs: Point[][] = lonLat.map((arc) =>
    simplify(
      arc.map(([lon, lat]) => project(nearLon(lon), clamp(lat, NEAR.s, NEAR.n))),
      SIMPLIFY_KM,
    ),
  );

  // ---- Countries in view ----
  const countries = topo.objects.countries.geometries.filter((g) => g.type === 'Polygon' || g.type === 'MultiPolygon');
  const polygonsOf = (g: Geometry): Ring[][] => (g.type === 'Polygon' ? [g.arcs as Ring[]] : (g.arcs as Ring[][]));
  const arcIds = (g: Geometry) => polygonsOf(g).flat(2).map((i) => (i < 0 ? ~i : i));
  const inView = countries.filter((g) =>
    arcIds(g).some((i) => arcs[i]?.some(([x, y]) => x >= CLIP.x && x <= CLIP.x + CLIP.w && y >= CLIP.y && y <= CLIP.y + CLIP.h)),
  );
  const norway = inView.find((g) => g.properties?.name === 'Norway');
  if (!norway) {
    console.error('Norway not found in the view');
    return 1;
  }

  const rings = (g: Geometry): Point[][] =>
    polygonsOf(g)
      .flatMap((polygon) => polygon.map((ring) => clipRing(stitch(ring, arcs), CLIP)))
      .filter((ring) => ring.length >= 3 && Math.abs(area(ring)) >= MIN_ISLAND_KM2);

  const norwayRings = rings(norway);
  const otherRings = inView.filter((g) => g !== norway).flatMap(rings);

  // ---- Strokes: coast (an arc used by one country) and land borders (shared) ----
  const uses = new Map<number, number>();
  for (const g of countries) for (const i of new Set(arcIds(g))) uses.set(i, (uses.get(i) ?? 0) + 1);
  const viewArcs = new Set(inView.flatMap(arcIds));
  const coast: Point[][] = [];
  const borders: Point[][] = [];
  for (const i of viewArcs) {
    const arc = arcs[i];
    if (!arc) continue;
    (uses.get(i) === 1 ? coast : borders).push(...clipLine(arc, CLIP));
  }

  // A real coastline never has a straight 150 km step; one means a ring went wrong.
  const jumps = longSteps([...norwayRings, ...otherRings], CLIP, true) + longSteps([...coast, ...borders], CLIP, false);
  if (jumps) {
    console.error(`${jumps} straight steps over 150 km away from the clip edge: the outline is broken`);
    return 1;
  }

  const out = {
    about:
      'Land, coastline and borders from Natural Earth 1:10m Admin 0 countries v4.1.0 (public domain), via world-atlas 2.0.2. Made by web/scripts/make-basemap.ts; do not edit by hand.',
    projection: PROJECTION,
    view: [VIEW.x, VIEW.y, VIEW.w, VIEW.h],
    countries: inView.map((g) => g.properties?.name ?? '?').sort(),
    norway: path(norwayRings, true),
    neighbours: path(otherRings, true),
    coast: path(coast.filter((l) => l.length >= 2), false),
    borders: path(borders.filter((l) => l.length >= 2), false),
  };
  const json = JSON.stringify(out);
  io.write(OUT, json + '\n');

  // ---- Report ----
  const points = (rs: Point[][]) => rs.reduce((n, r) => n + r.length, 0);
  console.log(`wrote ${OUT}: ${Math.round(json.length / 1024)} KB`);
  console.log(`  countries in view: ${out.countries.join(', ')}`);
  console.log(`  Norway: ${norwayRings.length} rings, ${points(norwayRings)} points; neighbours: ${otherRings.length} rings, ${points(otherRings)} points`);
  console.log(`  coast: ${coast.length} lines, ${points(coast)} points; borders: ${borders.length} lines`);
  const mainland = norwayRings.flat().filter(([x, y]) => x > CLIP.x + 1 && x < CLIP.x + CLIP.w - 1 && y > CLIP.y + 1 && y < CLIP.y + CLIP.h - 1);
  console.log(`  Norway's extent: ${fmtRect(bounds(mainland))}`);

  const farmsText = io.read('public/data/farms.json');
  if (farmsText) {
    const farms = JSON.parse(farmsText) as { lat: number | null; lon: number | null }[];
    const pts = farms.filter((f) => f.lat !== null && f.lon !== null).map((f) => project(f.lon!, f.lat!));
    const outside = pts.filter(([x, y]) => x < VIEW.x || x > VIEW.x + VIEW.w || y < VIEW.y || y > VIEW.y + VIEW.h);
    const onLand = pts.filter((p) => inside(p, norwayRings)).length;
    console.log(`  farms' extent: ${fmtRect(bounds(pts))}; ${outside.length} outside the view`);
    console.log(`  ${onLand} of ${pts.length} farms sit on land at this detail (narrow sounds and small islands aren't in a 1:10m map)`);
    if (outside.length) return 1;
  }
  return 0;
}

const fmtRect = (r: Rect) => `x ${r.x.toFixed(0)} to ${(r.x + r.w).toFixed(0)}, y ${r.y.toFixed(0)} to ${(r.y + r.h).toFixed(0)} km`;

/** Join a ring's arcs (a negative index means the arc reversed), dropping the repeated joints. */
function stitch(ring: Ring, arcs: Point[][]): Point[] {
  const out: Point[] = [];
  for (const i of ring) {
    const arc = arcs[i < 0 ? ~i : i];
    if (!arc) return [];
    const pts = i < 0 ? [...arc].reverse() : arc;
    out.push(...(out.length ? pts.slice(1) : pts));
  }
  return out;
}

/** Douglas–Peucker that keeps both end points, so arcs still meet at their joints. */
function simplify(pts: Point[], tol: number): Point[] {
  if (pts.length <= 2) return pts;
  const keep = new Uint8Array(pts.length);
  keep[0] = 1;
  keep[pts.length - 1] = 1;
  const stack: [number, number][] = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop()!;
    let worst = -1;
    let at = -1;
    for (let i = a + 1; i < b; i++) {
      const d = segmentDistance(pts[i]!, pts[a]!, pts[b]!);
      if (d > worst) {
        worst = d;
        at = i;
      }
    }
    if (worst > tol && at > 0) {
      keep[at] = 1;
      stack.push([a, at], [at, b]);
    }
  }
  return pts.filter((_, i) => keep[i]);
}

function segmentDistance([px, py]: Point, [ax, ay]: Point, [bx, by]: Point): number {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/** Sutherland–Hodgman clip of a closed ring against a rectangle. */
function clipRing(ring: Point[], r: Rect): Point[] {
  const edges: [(p: Point) => boolean, (a: Point, b: Point) => Point][] = [
    [([x]) => x >= r.x, (a, b) => cross(a, b, 0, r.x)],
    [([x]) => x <= r.x + r.w, (a, b) => cross(a, b, 0, r.x + r.w)],
    [([, y]) => y >= r.y, (a, b) => cross(a, b, 1, r.y)],
    [([, y]) => y <= r.y + r.h, (a, b) => cross(a, b, 1, r.y + r.h)],
  ];
  let out = ring;
  for (const [isIn, cut] of edges) {
    if (!out.length) break;
    const input = out;
    out = [];
    let prev = input[input.length - 1]!;
    for (const cur of input) {
      if (isIn(cur)) {
        if (!isIn(prev)) out.push(cut(prev, cur));
        out.push(cur);
      } else if (isIn(prev)) {
        out.push(cut(prev, cur));
      }
      prev = cur;
    }
  }
  return out;
}

/** Where segment a→b crosses the line (axis 0: x = v, axis 1: y = v). */
function cross(a: Point, b: Point, axis: 0 | 1, v: number): Point {
  const t = (v - a[axis]) / (b[axis] - a[axis]);
  return axis === 0 ? [v, a[1] + t * (b[1] - a[1])] : [a[0] + t * (b[0] - a[0]), v];
}

/** Liang–Barsky clip of an open line, split into the runs that stay inside. */
function clipLine(line: Point[], r: Rect): Point[][] {
  const runs: Point[][] = [];
  let run: Point[] = [];
  for (let i = 1; i < line.length; i++) {
    const seg = clipSegment(line[i - 1]!, line[i]!, r);
    if (!seg) {
      if (run.length) runs.push(run);
      run = [];
      continue;
    }
    const [a, b] = seg;
    const last = run[run.length - 1];
    if (!last || last[0] !== a[0] || last[1] !== a[1]) {
      if (run.length) runs.push(run);
      run = [a];
    }
    run.push(b);
  }
  if (run.length) runs.push(run);
  return runs;
}

function clipSegment(a: Point, b: Point, r: Rect): [Point, Point] | null {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  let t0 = 0;
  let t1 = 1;
  const checks: [number, number][] = [
    [-dx, a[0] - r.x],
    [dx, r.x + r.w - a[0]],
    [-dy, a[1] - r.y],
    [dy, r.y + r.h - a[1]],
  ];
  for (const [p, q] of checks) {
    if (p === 0) {
      if (q < 0) return null;
      continue;
    }
    const t = q / p;
    if (p < 0) {
      if (t > t1) return null;
      if (t > t0) t0 = t;
    } else {
      if (t < t0) return null;
      if (t < t1) t1 = t;
    }
  }
  const at = (t: number): Point => (t === 0 ? a : t === 1 ? b : [a[0] + t * dx, a[1] + t * dy]);
  return [at(t0), at(t1)];
}

/** Steps longer than 150 km that don't run along the clip rectangle's edge. */
function longSteps(lines: Point[][], r: Rect, closed: boolean): number {
  const onEdge = ([x, y]: Point) =>
    Math.abs(x - r.x) < 0.01 || Math.abs(x - r.x - r.w) < 0.01 || Math.abs(y - r.y) < 0.01 || Math.abs(y - r.y - r.h) < 0.01;
  let n = 0;
  for (const line of lines) {
    const last = closed ? line.length : line.length - 1;
    for (let i = 0; i < last; i++) {
      const a = line[i]!;
      const b = line[(i + 1) % line.length]!;
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) > 150 && !(onEdge(a) && onEdge(b))) n++;
    }
  }
  return n;
}

/** Signed area in km² (shoelace). */
function area(ring: Point[]): number {
  let s = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) s += (ring[j]![0] - ring[i]![0]) * (ring[j]![1] + ring[i]![1]);
  return s / 2;
}

/** Even-odd point in polygon over all rings. */
function inside([px, py]: Point, rings: Point[][]): boolean {
  let hit = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i]!;
      const [xj, yj] = ring[j]!;
      if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) hit = !hit;
    }
  }
  return hit;
}

/** Compact SVG path: absolute start, then relative steps, 0.1 km precision. */
function path(lines: Point[][], close: boolean): string {
  let out = '';
  for (const line of lines) {
    const pts = line.map(([x, y]) => [Math.round(x * 10), Math.round(y * 10)] as const);
    let [px, py] = pts[0]!;
    let body = '';
    let steps = 0;
    for (let i = 1; i < pts.length; i++) {
      const [x, y] = pts[i]!;
      if (x === px && y === py) continue;
      body += (steps ? sep(x - px) : '') + num(x - px) + sep(y - py) + num(y - py);
      px = x;
      py = y;
      steps++;
    }
    if (steps < (close ? 2 : 1)) continue;
    const [x0, y0] = pts[0]!;
    out += `M${num(x0)}${sep(y0)}${num(y0)}l${body}${close ? 'z' : ''}`;
  }
  return out;
}

/** A tenth of a kilometre as short text: 12 → "1.2", -5 → "-.5", 30 → "3". */
function num(tenths: number): string {
  const sign = tenths < 0 ? '-' : '';
  const a = Math.abs(tenths);
  const whole = Math.floor(a / 10);
  const frac = a % 10;
  return sign + (frac ? `${whole || ''}.${frac}` : String(whole));
}

/** A space between numbers, except before a minus sign, which separates on its own. */
const sep = (tenths: number) => (tenths < 0 ? '' : ' ');
