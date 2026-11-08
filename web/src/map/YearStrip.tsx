// The year strip under the map: one row per production area (north at the
// top, like the map), one column per week, coloured by the area's average for
// the map's layer. It's also the time control: click or drag to pick a week.
// Keyboards use the range input that sits behind it.

import { useMemo, useRef, useState, type PointerEvent } from 'react';
import type { FarmWeeksYear } from '../data/schemas';
import { rampColor, type LayerKey, type Ramp } from './scales';
import { AREA_NAMES, weekDates, weekMonth, weekNumber } from './text';

/** Production areas from the far north (13) to the south (1): the strip's rows. */
export const AREAS_NORTH_FIRST = [13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1];

export type AreaWeeks = {
  area: number;
  /** The average over the farms that reported, week by week; null if none did. */
  mean: Record<LayerKey, (number | null)[]>;
  /** How many farms reported, week by week. */
  count: Record<LayerKey, number[]>;
};

const LAYER_KEYS: LayerKey[] = ['lice', 'temp', 'treated', 'disease'];

/**
 * Every area's average for every layer and week of one year file, north first.
 * Treated and flagged are 1 or 0, so their average is the share of farms.
 */
export function areaWeeks(data: FarmWeeksYear, areaOf: (id: number) => number | undefined): AreaWeeks[] {
  const n = data.weeks.length;
  const areas = data.ids.map(areaOf);
  const grids: Record<LayerKey, (number | null)[][] | undefined> = {
    lice: data.mobile,
    temp: data.temp,
    treated: data.treated,
    disease: data.disease,
  };
  return AREAS_NORTH_FIRST.map((area) => {
    const mean = {} as AreaWeeks['mean'];
    const count = {} as AreaWeeks['count'];
    for (const key of LAYER_KEYS) {
      const grid = grids[key];
      mean[key] = Array.from({ length: n }, () => null);
      count[key] = Array.from({ length: n }, () => 0);
      if (!grid) continue;
      for (let w = 0; w < n; w++) {
        const row = grid[w] ?? [];
        let sum = 0;
        let k = 0;
        for (let j = 0; j < row.length; j++) {
          const v = row[j];
          if (v === null || v === undefined || areas[j] !== area) continue;
          sum += v;
          k += 1;
        }
        mean[key][w] = k ? sum / k : null;
        count[key][w] = k;
      }
    }
    return { area, mean, count };
  });
}

type Props = {
  rows: AreaWeeks[];
  layer: LayerKey;
  weeks: string[];
  /** The week on the map, as an index into `weeks`. */
  at: number;
  ramp: Ramp;
  /** One area-week in words, for the tooltip: "0.84 lice per fish, 52 farms". */
  describe: (v: number, farms: number) => string;
  /** The areas in the zoomed-in region; the other rows are dimmed. Null: all. */
  focus: number[] | null;
  inputId: string;
  valueText: string;
  onWeek: (i: number) => void;
};

const NO_DATA = 'rgba(255, 255, 255, 0.05)';
const QUARTERS = new Set(['Jan', 'Apr', 'Jul', 'Oct']);

export function YearStrip({ rows, layer, weeks, at, ramp, describe, focus, inputId, valueText, onWeek }: Props) {
  const plot = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  // The hovered cell, and how much room the plot has either side of it (px).
  const [hover, setHover] = useState<{ r: number; w: number; left: number; right: number } | null>(null);
  const n = Math.max(weeks.length, 1);

  // Runs of the same colour become one rectangle: fewer nodes, no seams.
  const cells = useMemo(
    () =>
      rows.flatMap((row, r) => {
        const out: { x: number; w: number; fill: string }[] = [];
        row.mean[layer].forEach((v, x) => {
          const fill = v === null ? NO_DATA : rampColor(ramp, v);
          const last = out[out.length - 1];
          if (last && last.fill === fill && last.x + last.w === x) last.w += 1;
          else out.push({ x, w: 1, fill });
        });
        return out.map((c) => <rect key={`${r}-${c.x}`} x={c.x} y={r} width={c.w} height={1} fill={c.fill} />);
      }),
    [rows, layer, ramp],
  );

  const months = useMemo(() => {
    const out: { i: number; label: string }[] = [];
    let prev = '';
    weeks.forEach((wk, i) => {
      const m = weekMonth(wk);
      if (m !== prev && QUARTERS.has(m)) out.push({ i, label: m });
      prev = m;
    });
    return out;
  }, [weeks]);

  const cellAt = (e: PointerEvent<HTMLDivElement>) => {
    const box = plot.current!.getBoundingClientRect();
    const w = Math.min(n - 1, Math.max(0, Math.floor(((e.clientX - box.left) / box.width) * n)));
    const r = Math.min(rows.length - 1, Math.max(0, Math.floor(((e.clientY - box.top) / box.height) * rows.length)));
    const x = ((w + 0.5) / n) * box.width;
    return { w, r, left: x, right: box.width - x };
  };

  const tip = hover ? rows[hover.r] : undefined;
  const tipValue = tip ? tip.mean[layer][hover!.w] ?? null : null;
  const tipCount = tip ? tip.count[layer][hover!.w] ?? 0 : 0;
  const tipX = hover ? (hover.w + 0.5) / n : 0;
  // The tooltip is up to 260px wide: centred over the cell unless that would
  // run past the map's right edge (the plot ends 1rem short of it) or its left.
  const tipAlign = !hover ? '' : hover.right < 120 ? ' is-end' : hover.left < 40 ? ' is-start' : '';

  return (
    <div className="year-strip">
      <div className="ys-side" aria-hidden="true">
        <span>North</span>
        <span>South</span>
      </div>
      <div
        ref={plot}
        className="ys-plot"
        onPointerDown={(e) => {
          if (e.button !== 0) return;
          e.currentTarget.setPointerCapture(e.pointerId);
          dragging.current = true;
          const c = cellAt(e);
          setHover(e.pointerType === 'mouse' ? c : null);
          onWeek(c.w);
        }}
        onPointerMove={(e) => {
          const c = cellAt(e);
          if (dragging.current && c.w !== at) onWeek(c.w);
          if (e.pointerType === 'mouse' && (c.w !== hover?.w || c.r !== hover?.r)) setHover(c);
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onPointerCancel={() => {
          dragging.current = false;
        }}
        onPointerLeave={() => setHover(null)}
      >
        <svg viewBox={`0 0 ${n} ${rows.length}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
          <g shapeRendering="crispEdges">{cells}</g>
          {/* Thin gaps between areas; weeks run on without a break. */}
          <path
            className="ys-gaps"
            d={rows
              .slice(1)
              .map((_, r) => `M0 ${r + 1}H${n}`)
              .join('')}
          />
          {focus
            ? rows.map((row, r) => (focus.includes(row.area) ? null : <rect key={row.area} className="ys-dim" x={0} y={r} width={n} height={1} />))
            : null}
          {hover ? <rect className="ys-hover" x={hover.w} y={hover.r} width={1} height={1} /> : null}
          <rect className="ys-now" x={at} y={-0.35} width={1} height={rows.length + 0.7} />
        </svg>
        {tip && hover ? (
          <div
            className={`ys-tip${tipAlign}`}
            style={{ left: `${tipX * 100}%` }}
            aria-hidden="true"
          >
            <strong>
              Area {tip.area}
              {AREA_NAMES[tip.area] ? `, ${AREA_NAMES[tip.area]}` : ''}
            </strong>
            <span>
              Week {weekNumber(weeks[hover.w] ?? '')}, {weekDates(weeks[hover.w] ?? '')}
            </span>
            <span className="ys-tip-value">{tipValue === null ? 'No reports' : describe(tipValue, tipCount)}</span>
          </div>
        ) : null}
      </div>
      <div className="ys-scale" aria-hidden="true">
        {months.map((m) => (
          <span key={m.label} style={{ left: `${(m.i / n) * 100}%` }}>
            {m.label}
          </span>
        ))}
      </div>
      <label htmlFor={inputId} className="sr-only">
        Week
      </label>
      <input
        id={inputId}
        className="sr-only"
        type="range"
        min={0}
        max={Math.max(weeks.length - 1, 0)}
        step={1}
        value={at}
        aria-valuetext={valueText}
        onChange={(e) => onWeek(Number(e.target.value))}
      />
    </div>
  );
}
