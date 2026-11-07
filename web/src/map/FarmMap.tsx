// The farm map: Norway's coast (public/map/norway.json) with one dot per farm.
//
// Two stacked canvases share one projection (./projection.ts): the land and
// labels underneath, redrawn only when the view or size changes, and the farm
// dots on top, redrawn when the week, layer or hover changes. Changing week
// fades the colours over a fifth of a second; changing region glides the view.
// Both are instant for people who ask for reduced motion.

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { prefersReducedMotion } from '../components/Bits';
import type { Basemap } from './basemap';
import { AREA_SPOTS, CITIES, COUNTRIES, SEAS } from './places';
import { fit, lerpRect, project, type Rect } from './projection';
import { MAP, type Mark } from './scales';

export type MapPoint = { id: number; col: number; x: number; y: number };

type Props = {
  basemap: Basemap | null;
  points: MapPoint[];
  /** One mark per point, in the same order. */
  marks: Mark[];
  view: Rect;
  selectedId: number | null;
  selectedLabel: string | null;
  showAreas: boolean;
  /** Accessible summary of what the map shows this week. */
  label: string;
  tooltip: (i: number) => ReactNode;
  onPick: (id: number) => void;
};

const FADE_MS = 220;
const GLIDE_MS = 650;
const HOVER_PX = 14;
const TOUCH_PX = 24;

type Size = { w: number; h: number; dpr: number };
type Paths = { norway: Path2D; neighbours: Path2D; coast: Path2D; borders: Path2D };

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const dotRadius = (k: number) => Math.max(2.1, Math.min(5, 1.2 + 2.6 * Math.sqrt(k)));

const rgbCache = new Map<string, [number, number, number]>();
function rgb(hex: string): [number, number, number] {
  let c = rgbCache.get(hex);
  if (!c) {
    const n = parseInt(hex.slice(1), 16);
    c = [n >> 16, (n >> 8) & 255, n & 255];
    rgbCache.set(hex, c);
  }
  return c;
}
function mix(a: string, b: string, t: number): string {
  const x = rgb(a);
  const y = rgb(b);
  return `rgb(${Math.round(x[0] + (y[0] - x[0]) * t)},${Math.round(x[1] + (y[1] - x[1]) * t)},${Math.round(x[2] + (y[2] - x[2]) * t)})`;
}

// Labels are projected once.
const cityXY = CITIES.map((c) => ({ ...c, xy: project(c.lon, c.lat) }));
const countryXY = COUNTRIES.map((c) => ({ ...c, xy: project(c.lon, c.lat) }));
const seaXY = SEAS.map((c) => ({ ...c, xy: project(c.lon, c.lat) }));
const areaXY = Object.entries(AREA_SPOTS).map(([area, [lon, lat]]) => ({ area, xy: project(lon, lat) }));

export function FarmMap({ basemap, points, marks, view, selectedId, selectedLabel, showAreas, label, tooltip, onPick }: Props) {
  const stageRef = useRef<HTMLDivElement>(null);
  const baseRef = useRef<HTMLCanvasElement>(null);
  const dotsRef = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState<Size | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [gliding, setGliding] = useState(false);

  // Everything the draw loop reads lives in refs, so a frame never waits on React.
  const paths = useRef<Paths | null>(null);
  const drawn = useRef<Rect>(view); // the view on screen right now
  const glide = useRef<{ from: Rect; to: Rect; start: number } | null>(null);
  const fade = useRef<{ from: Mark[]; start: number } | null>(null);
  const shown = useRef<{ points: MapPoint[]; marks: Mark[] }>({ points, marks });
  const frame = useRef(0);
  const baseDirty = useRef(true);
  const live = useRef({ size, hover, selectedId, selectedLabel, showAreas });
  live.current = { size, hover, selectedId, selectedLabel, showAreas };
  const pointerType = useRef('mouse');

  // Draw order: lowest rank first, so high values sit on top.
  const order = useMemo(() => {
    const idx = points.map((_, i) => i);
    return idx.sort((a, b) => (marks[a]?.rank ?? 0) - (marks[b]?.rank ?? 0));
  }, [points, marks]);
  const orderRef = useRef(order);
  orderRef.current = order;

  const schedule = () => {
    if (!frame.current) frame.current = requestAnimationFrame(tick);
  };

  function tick(now: number) {
    frame.current = 0;
    const s = live.current.size;
    if (!s) return;
    let again = false;

    const g = glide.current;
    if (g) {
      const u = Math.min(1, (now - g.start) / GLIDE_MS);
      drawn.current = lerpRect(g.from, g.to, ease(u));
      baseDirty.current = true;
      if (u < 1) again = true;
      else {
        glide.current = null;
        setGliding(false);
      }
    }
    if (baseDirty.current) {
      drawBase(s);
      baseDirty.current = false;
    }

    let t = 1;
    const f = fade.current;
    if (f) {
      t = Math.min(1, (now - f.start) / FADE_MS);
      if (t < 1) again = true;
      else fade.current = null;
    }
    drawDots(s, t, f?.from ?? null);
    if (again) schedule();
  }

  function drawBase({ w, h, dpr }: Size) {
    const ctx = baseRef.current?.getContext('2d');
    if (!ctx) return;
    const v = drawn.current;
    const { k, tx, ty } = fit(v, w, h);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = MAP.sea;
    ctx.fillRect(0, 0, w, h);
    const p = paths.current;
    if (p) {
      ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * tx, dpr * ty);
      ctx.fillStyle = MAP.neighbours;
      ctx.fill(p.neighbours, 'evenodd');
      ctx.fillStyle = MAP.norway;
      ctx.fill(p.norway, 'evenodd');
      ctx.lineJoin = 'round';
      ctx.lineWidth = 0.8 / k;
      ctx.strokeStyle = MAP.coast;
      ctx.stroke(p.coast);
      ctx.setLineDash([3 / k, 3 / k]);
      ctx.lineWidth = 0.9 / k;
      ctx.strokeStyle = MAP.border;
      ctx.stroke(p.borders);
      ctx.setLineDash([]);
    }

    // Labels, in screen pixels so they stay the same size at any zoom; a bit
    // smaller on a small map, and always kept inside the frame.
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    const small = k < 0.35;
    const at = ([x, y]: [number, number]) => [x * k + tx, y * k + ty] as const;
    const spaced = 'letterSpacing' in ctx;
    const setSpacing = (px: number) => {
      if (spaced) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${px}px`;
    };
    const centred = (text: string, x: number, y: number) => {
      const half = ctx.measureText(text).width / 2;
      ctx.fillText(text, Math.min(Math.max(x, half + 6), w - half - 6), y);
    };

    for (const c of countryXY) {
      const [x, y] = at(c.xy);
      const size = (c.main ? 13 : 11) * (small ? 0.8 : 1);
      ctx.font = `${c.main ? 700 : 650} ${size}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
      setSpacing((c.main ? 5 : 3) * (small ? 0.5 : 1));
      ctx.textAlign = 'center';
      ctx.fillStyle = c.main ? MAP.label : MAP.labelSoft;
      ctx.globalAlpha = c.main ? 0.9 : 0.75;
      centred(c.name, x, y);
    }
    ctx.globalAlpha = 1;
    setSpacing(0);

    ctx.font = `italic 400 ${small ? 10.5 : 12}px Charter, "Bitstream Charter", Cambria, Georgia, serif`;
    ctx.fillStyle = MAP.labelSoft;
    ctx.textAlign = 'center';
    for (const s of seaXY) {
      const [x, y] = at(s.xy);
      centred(s.name, x, y);
    }

    if (live.current.showAreas) {
      const r = small ? 7.5 : 9;
      ctx.font = `700 ${small ? 9 : 10.5}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
      ctx.textAlign = 'center';
      for (const a of areaXY) {
        const [x, y] = at(a.xy);
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(20, 33, 48, 0.9)';
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = MAP.labelSoft;
        ctx.stroke();
        ctx.fillStyle = MAP.label;
        ctx.fillText(a.area, x, y + 0.5);
      }
    }
  }

  function drawDots({ w, h, dpr }: Size, t: number, from: Mark[] | null) {
    const ctx = dotsRef.current?.getContext('2d');
    if (!ctx) return;
    const { points: pts, marks: mks } = shown.current;
    const { k, tx, ty } = fit(drawn.current, w, h);
    const r = dotRadius(k);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.lineJoin = 'round';

    for (const i of orderRef.current) {
      const p = pts[i];
      const to = mks[i];
      if (!p || !to) continue;
      const x = p.x * k + tx;
      const y = p.y * k + ty;
      if (x < -12 || y < -12 || x > w + 12 || y > h + 12) continue;
      const was = from?.[i] ?? to;
      const blend = t < 1 && was !== to;
      const fill = blend ? mix(was.fill, to.fill, t) : to.fill;
      const shape = blend && t < 0.5 ? was.shape : to.shape;
      const ring = blend ? (was.ring ? 1 - t : 0) + (to.ring ? t : 0) : to.ring ? 1 : 0;

      if (shape === 'empty') {
        ctx.beginPath();
        ctx.arc(x, y, r * 0.72, 0, Math.PI * 2);
        ctx.lineWidth = 1;
        ctx.strokeStyle = fill;
        ctx.stroke();
        continue;
      }
      ctx.beginPath();
      if (shape === 'diamond') {
        const d = r * 1.45;
        ctx.moveTo(x, y - d);
        ctx.lineTo(x + d, y);
        ctx.lineTo(x, y + d);
        ctx.lineTo(x - d, y);
        ctx.closePath();
      } else {
        ctx.arc(x, y, r, 0, Math.PI * 2);
      }
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = MAP.sea;
      ctx.stroke();
      if (ring > 0) {
        ctx.globalAlpha = ring;
        ctx.beginPath();
        ctx.arc(x, y, r + 2.3, 0, Math.PI * 2);
        ctx.lineWidth = 1.3;
        ctx.strokeStyle = MAP.ring;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
    }

    // City names go on top of the dots, with a halo, so they stay readable.
    ctx.font = `600 ${k < 0.35 ? 10.5 : 11.5}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    for (const c of cityXY) {
      const x = c.xy[0] * k + tx;
      const y = c.xy[1] * k + ty;
      ctx.beginPath();
      ctx.arc(x, y, 2.6, 0, Math.PI * 2);
      ctx.fillStyle = MAP.label;
      ctx.fill();
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = MAP.sea;
      ctx.stroke();
      ctx.lineWidth = 3.5;
      ctx.strokeText(c.name, x + 6, y);
      ctx.fillText(c.name, x + 6, y);
    }

    const { hover: hv, selectedId: sel, selectedLabel: selLabel } = live.current;
    if (hv !== null && pts[hv] && pts[hv].id !== sel) {
      const p = pts[hv];
      ctx.beginPath();
      ctx.arc(p.x * k + tx, p.y * k + ty, r + 3.6, 0, Math.PI * 2);
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.stroke();
    }
    const si = sel === null ? -1 : pts.findIndex((p) => p.id === sel);
    if (si >= 0) {
      const p = pts[si]!;
      const x = p.x * k + tx;
      const y = p.y * k + ty;
      ctx.beginPath();
      ctx.arc(x, y, r + 5, 0, Math.PI * 2);
      ctx.lineWidth = 4.5;
      ctx.strokeStyle = MAP.sea;
      ctx.stroke();
      ctx.lineWidth = 2.2;
      ctx.strokeStyle = '#ffffff';
      ctx.stroke();
      if (selLabel) {
        ctx.font = '700 12.5px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
        ctx.textBaseline = 'middle';
        const width = ctx.measureText(selLabel).width;
        const right = x + r + 10 + width < w - 6;
        ctx.textAlign = right ? 'left' : 'right';
        const lx = right ? x + r + 10 : x - r - 10;
        ctx.lineWidth = 4;
        ctx.strokeStyle = MAP.sea;
        ctx.strokeText(selLabel, lx, y);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(selLabel, lx, y);
      }
    }
  }

  // Size the canvases to the stage.
  useLayoutEffect(() => {
    const el = stageRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
      setSize((old) => (old && old.w === r.width && old.h === r.height && old.dpr === dpr ? old : { w: r.width, h: r.height, dpr }));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useLayoutEffect(() => {
    if (!size) return;
    for (const c of [baseRef.current, dotsRef.current]) {
      if (!c) continue;
      c.width = Math.round(size.w * size.dpr);
      c.height = Math.round(size.h * size.dpr);
    }
    baseDirty.current = true;
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [size]);

  useEffect(() => {
    paths.current = basemap
      ? { norway: new Path2D(basemap.norway), neighbours: new Path2D(basemap.neighbours), coast: new Path2D(basemap.coast), borders: new Path2D(basemap.borders) }
      : null;
    baseDirty.current = true;
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap]);

  useEffect(() => {
    baseDirty.current = true;
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showAreas]);

  // Glide to a new view.
  useEffect(() => {
    const from = drawn.current;
    if (from.x === view.x && from.y === view.y && from.w === view.w && from.h === view.h) return;
    if (prefersReducedMotion() || !live.current.size) {
      drawn.current = view;
      glide.current = null;
      baseDirty.current = true;
    } else {
      glide.current = { from, to: view, start: performance.now() };
      setGliding(true);
      setHover(null);
    }
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view]);

  // Fade to the new week or layer (only when the same farms are on the map).
  useEffect(() => {
    const prev = shown.current;
    const same = prev.points === points && prev.marks.length === marks.length;
    fade.current = same && prev.marks !== marks && !prefersReducedMotion() ? { from: prev.marks, start: performance.now() } : null;
    shown.current = { points, marks };
    if (!same) setHover(null);
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, marks]);

  useEffect(() => {
    schedule();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hover, selectedId, selectedLabel]);

  useEffect(
    () => () => {
      // Reset the handle too: React's dev mode mounts twice, and a stale handle
      // would make every later schedule() think a frame is already on its way.
      cancelAnimationFrame(frame.current);
      frame.current = 0;
    },
    [],
  );

  const nearest = (clientX: number, clientY: number, radius: number): number | null => {
    const el = stageRef.current;
    const s = live.current.size;
    if (!el || !s) return null;
    const box = el.getBoundingClientRect();
    const px = clientX - box.left;
    const py = clientY - box.top;
    const { k, tx, ty } = fit(drawn.current, s.w, s.h);
    let best: number | null = null;
    let bestD = radius * radius;
    const pts = shown.current.points;
    for (let i = 0; i < pts.length; i++) {
      const dx = pts[i]!.x * k + tx - px;
      const dy = pts[i]!.y * k + ty - py;
      const d = dx * dx + dy * dy;
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    }
    return best;
  };

  // Where the hovered farm is on screen, for the tooltip.
  let tip: { x: number; y: number; left: boolean; up: boolean } | null = null;
  if (hover !== null && size && !gliding && points[hover]) {
    const { k, tx, ty } = fit(drawn.current, size.w, size.h);
    const x = points[hover].x * k + tx;
    const y = points[hover].y * k + ty;
    tip = { x, y, left: x > size.w * 0.55, up: y > size.h * 0.35 };
  }

  return (
    <div
      ref={stageRef}
      className={`map-stage${hover !== null ? ' is-pointing' : ''}`}
      role="img"
      aria-label={label}
      onPointerDown={(e) => {
        pointerType.current = e.pointerType;
      }}
      onPointerMove={(e) => {
        if (e.pointerType !== 'mouse' || glide.current) return;
        const i = nearest(e.clientX, e.clientY, HOVER_PX);
        if (i !== hover) setHover(i);
      }}
      onPointerLeave={() => setHover(null)}
      onClick={(e) => {
        // A mouse picks exactly the farm that's highlighted; touch finds the nearest.
        const mouse = pointerType.current === 'mouse';
        const i = mouse && hover !== null ? hover : nearest(e.clientX, e.clientY, mouse ? HOVER_PX : TOUCH_PX);
        if (i !== null && shown.current.points[i]) onPick(shown.current.points[i]!.id);
      }}
    >
      <canvas ref={baseRef} className="map-canvas" aria-hidden="true" />
      <canvas ref={dotsRef} className="map-canvas" aria-hidden="true" />
      {!basemap ? <p className="map-loading">Drawing the coast…</p> : null}
      {tip ? (
        <div
          className={`map-tip${tip.left ? ' is-left' : ''}${tip.up ? ' is-up' : ''}`}
          style={{ left: tip.x, top: tip.y }}
          aria-hidden="true"
        >
          {tooltip(hover!)}
        </div>
      ) : null}
    </div>
  );
}
