import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Numbers, Table } from '../components/Bits';
import { DASH, fmt, fmtInt, mean } from '../components/format';
import { IconPause, IconPlay } from '../components/Icons';
import { Later, StatusView } from '../components/States';
import type { Status } from '../data/load';
import type { Farms, FarmWeeksIndex, FarmWeeksYear } from '../data/schemas';
import { loadFarmWeeksYear, useFarmWeeksYear, type Source } from '../data/source';
import { useBasemap } from '../map/basemap';
import { FarmCard } from '../map/FarmCard';
import { FarmMap, type MapPoint } from '../map/FarmMap';
import { FarmSearch } from '../map/FarmSearch';
import { MapKey } from '../map/MapKey';
import { VIEW, bounds, padRect, project, type Rect } from '../map/projection';
import { layerInfo, markFor, type LayerKey, type Values } from '../map/scales';
import { AREA_NAMES, areaLabel, displayName, weekDates, weekMonth, weekNumber } from '../map/text';

type Props = { farms: Status<Farms>; index: Status<FarmWeeksIndex>; source: Source };

/** Finding 1: farms.json, farm_weeks/index.json, then one year file at a time. */
export function FarmSection({ farms, index, source }: Props) {
  return (
    <StatusView status={farms} file="farms.json" owner="Data" due="21:30">
      {(farmList) => (
        <StatusView status={index} file="farm_weeks/index.json" owner="Data" due="21:30">
          {(idx) => <FarmYears farms={farmList} years={idx.years} source={source} />}
        </StatusView>
      )}
    </StatusView>
  );
}

/** Loads the chosen year; keeps the last year on screen while the next one loads. */
function FarmYears({ farms, years, source }: { farms: Farms; years: number[]; source: Source }) {
  const sorted = useMemo(() => [...years].sort((a, b) => a - b), [years]);
  const [year, setYear] = useState<number | null>(sorted[sorted.length - 1] ?? null);
  const status = useFarmWeeksYear(year, source);
  const [last, setLast] = useState<FarmWeeksYear | null>(null);
  const [seen, setSeen] = useState(status);
  if (status !== seen) {
    setSeen(status);
    if (status?.state === 'ok') setLast(status.data);
  }

  if (!sorted.length || year === null) {
    return (
      <Later>
        <p>No years listed yet.</p>
        <p className="note">
          Waiting for years in <code>farm_weeks/index.json</code> from Data.
        </p>
      </Later>
    );
  }
  const data = status?.state === 'ok' ? status.data : last;
  const problem = status && status.state !== 'ok' && status.state !== 'loading' ? status : null;
  if (!data || problem) {
    return (
      <div className="farm-panel">
        <YearChips years={sorted} year={year} onYear={setYear} />
        <StatusView status={status ?? { state: 'loading' }} file={`farm_weeks/${year}.json`} owner="Data" due="21:30">
          {() => null}
        </StatusView>
      </div>
    );
  }
  return <FarmExplorer farms={farms} years={sorted} year={year} onYear={setYear} data={data} source={source} />;
}

function YearChips({ years, year, onYear }: { years: number[]; year: number; onYear: (y: number) => void }) {
  const name = useId();
  return (
    <fieldset className="chips">
      <legend>Year</legend>
      {years.map((y) => (
        <label key={y} className="chip">
          <input type="radio" name={name} value={y} checked={y === year} onChange={() => onYear(y)} />
          <span>{y}</span>
        </label>
      ))}
    </fieldset>
  );
}

type RegionKey = 'all' | 'south' | 'middle' | 'north';
const REGIONS: { key: RegionKey; label: string; areas: number[] | null }[] = [
  { key: 'all', label: 'Whole coast', areas: null },
  { key: 'south', label: 'South and west', areas: [1, 2, 3, 4, 5] },
  { key: 'middle', label: 'Middle', areas: [6, 7, 8] },
  { key: 'north', label: 'North', areas: [9, 10, 11, 12, 13] },
];

const STEP_MS = 420;

type ExplorerProps = {
  farms: Farms;
  years: number[];
  /** The year asked for. `data` may still be the previous year while it loads. */
  year: number;
  onYear: (y: number) => void;
  data: FarmWeeksYear;
  source: Source;
};

/** The map, its controls, the chosen farm and the week's numbers. */
export function FarmExplorer({ farms, years, year, onYear, data, source }: ExplorerProps) {
  const basemap = useBasemap();
  const [week, setWeek] = useState(() => weekNumber(data.weeks[data.weeks.length - 1] ?? ''));
  const [layer, setLayer] = useState<LayerKey>('lice');
  const [region, setRegion] = useState<RegionKey>('all');
  const [selected, setSelected] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [showAreas, setShowAreas] = useState(true);
  const zoomName = useId();
  const sliderId = useId();
  const yearId = useId();

  const loading = data.year !== year;
  // While the next year loads, hold the week that's on screen.
  const held = useRef(data.weeks.length - 1);
  let at = held.current;
  if (!loading) {
    at = indexOfWeek(data.weeks, week);
    held.current = at;
  }
  const weekLabel = data.weeks[at] ?? '';
  const activeLayer: LayerKey = layer === 'disease' && !data.disease ? 'lice' : layer;

  const byId = useMemo(() => new Map(farms.map((f) => [f.id, f])), [farms]);
  const areas = useMemo(() => areaSummary(data, at, byId), [data, at, byId]);
  const points = useMemo<MapPoint[]>(() => {
    const out: MapPoint[] = [];
    data.ids.forEach((id, col) => {
      const f = byId.get(id);
      if (!f || f.lat === null || f.lon === null) return;
      const [x, y] = project(f.lon, f.lat);
      out.push({ id, col, x, y });
    });
    return out;
  }, [data, byId]);
  const colOf = useMemo(() => new Map(data.ids.map((id, col) => [id, col])), [data]);
  const unplaced = data.ids.length - points.length;

  const values = (col: number): Values => ({
    mobile: data.mobile[at]?.[col] ?? null,
    temp: data.temp[at]?.[col] ?? null,
    treated: data.treated[at]?.[col] ?? null,
    disease: data.disease?.[at]?.[col] ?? null,
  });
  const marks = useMemo(
    () => points.map((p) => markFor(activeLayer, values(p.col))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [points, activeLayer, at, data],
  );

  const regionRects = useMemo(() => {
    const rects: Record<RegionKey, Rect> = { all: VIEW, south: VIEW, middle: VIEW, north: VIEW };
    for (const r of REGIONS) {
      if (!r.areas) continue;
      const pts = farms.filter((f) => r.areas!.includes(f.area) && f.lat !== null && f.lon !== null).map((f) => project(f.lon!, f.lat!));
      if (pts.length) rects[r.key] = padRect(bounds(pts), 45);
    }
    return rects;
  }, [farms]);

  // Playing: one week every STEP_MS, then on into the next year.
  useEffect(() => {
    if (!playing || loading) return;
    const t = window.setTimeout(() => {
      if (at < data.weeks.length - 1) {
        setWeek(weekNumber(data.weeks[at + 1]!));
        return;
      }
      const next = years.find((y) => y > year);
      if (next === undefined) setPlaying(false);
      else {
        setWeek(1);
        onYear(next);
      }
    }, STEP_MS);
    return () => window.clearTimeout(t);
  }, [playing, loading, at, data, year, years, onYear]);

  // Fetch next year's file before the play head gets there.
  useEffect(() => {
    if (!playing || at < data.weeks.length - 8) return;
    const next = years.find((y) => y > year);
    if (next !== undefined) void loadFarmWeeksYear(next, source);
  }, [playing, at, data, years, year, source]);

  const togglePlay = () => {
    if (playing) return setPlaying(false);
    const atEnd = at >= data.weeks.length - 1 && !years.some((y) => y > year);
    if (atEnd) setWeek(weekNumber(data.weeks[0] ?? ''));
    setPlaying(true);
  };

  const selectedFarm = selected === null ? null : (byId.get(selected) ?? null);
  const selectedCol = selected === null ? null : (colOf.get(selected) ?? null);
  const areaCols = useMemo(() => {
    if (!selectedFarm) return [];
    return data.ids.flatMap((id, col) => (byId.get(id)?.area === selectedFarm.area ? [col] : []));
  }, [data, byId, selectedFarm]);
  const reporting = useMemo(() => new Set(data.ids), [data]);

  const pickFarm = (id: number, fromSearch = false) => {
    setSelected(id);
    const f = byId.get(id);
    if (fromSearch && f && region !== 'all' && !REGIONS.find((r) => r.key === region)?.areas?.includes(f.area)) {
      setRegion(REGIONS.find((r) => r.areas?.includes(f.area))?.key ?? 'all');
    }
  };

  const reportingNow = (data.mobile[at] ?? []).filter((v) => v !== null).length;
  const info = layerInfo(activeLayer);
  const mapLabel =
    `Map of Norway's coast with ${fmtInt(points.length)} salmon farms. ${weekText(weekLabel)}: ` +
    `${fmtInt(reportingNow)} farms reported. Colour shows ${info.title.toLowerCase()}. ` +
    'The same numbers are in the table "This week by area" below the map.';

  const tooltip = (i: number) => {
    const p = points[i];
    const f = p ? byId.get(p.id) : undefined;
    if (!p || !f) return null;
    const v = values(p.col);
    return (
      <>
        <strong>{displayName(f.name)}</strong>
        <span className="map-tip-area">{areaLabel(f.area)}</span>
        {v.mobile === null && v.temp === null && v.treated === null ? (
          <span className="map-tip-none">No report this week</span>
        ) : (
          <dl>
            <div className={activeLayer === 'lice' ? 'is-on' : undefined}>
              <dt>Lice</dt>
              <dd>{v.mobile === null ? DASH : `${fmt(v.mobile)} per fish`}</dd>
            </div>
            <div className={activeLayer === 'temp' ? 'is-on' : undefined}>
              <dt>Sea</dt>
              <dd>{v.temp === null ? DASH : `${fmt(v.temp, 1)} °C`}</dd>
            </div>
            <div className={activeLayer === 'treated' ? 'is-on' : undefined}>
              <dt>Treated</dt>
              <dd>{v.treated === null ? DASH : v.treated === 1 ? 'Yes' : 'No'}</dd>
            </div>
            {data.disease ? (
              <div className={activeLayer === 'disease' ? 'is-on' : undefined}>
                <dt>ISA or PD</dt>
                <dd>{v.disease === null ? DASH : v.disease === 1 ? 'Flagged' : 'No'}</dd>
              </div>
            ) : null}
          </dl>
        )}
      </>
    );
  };

  const weekNo = weekNumber(weekLabel);

  // On a desktop the explorer is one screen tall (styles.css, "fits the screen"):
  // the map on the left, then the key and the week's numbers, then the chosen
  // farm or the week by area. Phones get the same parts stacked.
  return (
    <div className="farm-panel farm-explorer" id="farm-map">
      <div className="explorer-grid">
        <div className="map-panel">
          <div className="map-stage-wrap">
            <FarmMap
              basemap={basemap.state === 'ok' ? basemap.data : null}
              points={points}
              marks={marks}
              view={regionRects[region]}
              selectedId={selected}
              selectedLabel={selectedFarm ? displayName(selectedFarm.name) : null}
              showAreas={showAreas}
              label={mapLabel}
              tooltip={tooltip}
              onPick={(id) => pickFarm(id)}
            />
            <div className="map-overlay">
              <fieldset className="map-zoom">
                <legend className="sr-only">Zoom to</legend>
                {REGIONS.map((r) => (
                  <label key={r.key} className="map-pill">
                    <input type="radio" name={zoomName} value={r.key} checked={region === r.key} onChange={() => setRegion(r.key)} />
                    <span>{r.label}</span>
                  </label>
                ))}
              </fieldset>
              <p className="map-week">
                <span className="map-week-year">
                  {data.year}
                  {loading ? ` · loading ${year}…` : ''}
                </span>
                <span className="map-week-title">Week {weekNo || DASH}</span>
                <span className="map-week-dates">{weekDates(weekLabel)}</span>
              </p>
            </div>
          </div>
          {basemap.state !== 'ok' && basemap.state !== 'loading' ? (
            <p className="map-problem" role="status">
              The coastline file (map/{'norway.json'}) didn't load, so the farms are shown without the land.
            </p>
          ) : null}

          <div className="map-time">
            <button type="button" className="play-btn" onClick={togglePlay} aria-label={playing ? 'Pause' : 'Play through the weeks'}>
              {playing ? <IconPause size={20} /> : <IconPlay size={20} />}
            </button>
            <label htmlFor={yearId} className="sr-only">
              Year
            </label>
            <select id={yearId} className="year-select" value={year} onChange={(e) => onYear(Number(e.target.value))}>
              {years.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            {/* Phones show the week here; bigger screens show it over the map. */}
            <span className="map-time-week" aria-hidden="true">
              <strong>Week {weekNo || DASH}</strong> {weekDates(weekLabel)}
            </span>
            <div className="map-slider">
              <label htmlFor={sliderId} className="sr-only">
                Week
              </label>
              <input
                id={sliderId}
                type="range"
                min={0}
                max={Math.max(data.weeks.length - 1, 0)}
                step={1}
                value={at}
                aria-valuetext={weekText(weekLabel)}
                onChange={(e) => {
                  setPlaying(false);
                  setWeek(weekNumber(data.weeks[Number(e.target.value)] ?? ''));
                }}
              />
              <div className="map-slider-scale" aria-hidden="true">
                <span>{weekMonth(data.weeks[0] ?? '')}</span>
                <span>{weekMonth(data.weeks[data.weeks.length - 1] ?? '')}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="map-rail">
          <div className="map-rail-main">
            <MapKey layer={activeLayer} onLayer={setLayer} hasDisease={!!data.disease} showAreas={showAreas} onShowAreas={setShowAreas} />
            <FarmSearch farms={farms} reporting={reporting} year={data.year} onPick={(id) => pickFarm(id, true)} />
            <WeekStats data={data} at={at} />
          </div>
          <div className="map-detail">
            {selectedFarm ? (
              <FarmCard
                farm={selectedFarm}
                data={data}
                col={selectedCol}
                week={at}
                areaCols={areaCols}
                onWeek={(i) => {
                  setPlaying(false);
                  setWeek(weekNumber(data.weeks[i] ?? ''));
                }}
                onClose={() => setSelected(null)}
              />
            ) : (
              <>
                <p className="map-hint">Click a farm on the map, or find one by name, to see its year week by week.</p>
                <AreaBars rows={areas.areas} layer={activeLayer} />
              </>
            )}
          </div>
        </div>
      </div>

      {unplaced ? (
        <p className="warn" role="status">
          {fmtInt(unplaced)} farm IDs in this year's file aren't in farms.json or have no position, so they're not on the map. Tell Data.
        </p>
      ) : null}

      <Numbers title="This week by area">
        <AreaTable week={weekLabel} summary={areas} />
      </Numbers>

      <p className="note">
        {fmtInt(farms.length)} farms in the register; {fmtInt(data.ids.length)} reported at least once in {data.year}. Simple
        averages over the farms that reported; the analysis itself uses capacity-weighted indices. Coastline: Natural Earth
        (1:10m), so some farms in narrow sounds appear on land.
      </p>
    </div>
  );
}

const weekText = (week: string) => (week ? `Week ${weekNumber(week)}, ${weekDates(week)}` : 'No weeks yet');

/** The index of ISO week `n` in `weeks`, or the nearest week before it (or the first). */
export function indexOfWeek(weeks: string[], n: number): number {
  let best = 0;
  for (let i = 0; i < weeks.length; i++) {
    const w = weekNumber(weeks[i]!);
    if (w === n) return i;
    if (w < n) best = i;
  }
  return best;
}
/** The week's numbers for the whole coast, as a short list. */
function WeekStats({ data, at }: { data: FarmWeeksYear; at: number }) {
  const mobile = data.mobile[at] ?? [];
  const treated = (data.treated[at] ?? []).filter((v) => v !== null);
  const disease = data.disease?.[at];
  const reporting = mobile.filter((v) => v !== null).length;
  const treatedShare = treated.length ? treated.filter((v) => v === 1).length / treated.length : null;
  const rows: [string, string][] = [
    ['Farms reporting lice', `${fmtInt(reporting)} of ${fmtInt(data.ids.length)}`],
    ['Mobile lice per fish', fmt(mean(mobile))],
    ['Reporting farms treated', treatedShare === null ? DASH : `${(treatedShare * 100).toFixed(1)}%`],
    ['Sea temperature', `${fmt(mean(data.temp[at] ?? []), 1)} °C`],
    ['Farms flagged ISA or PD', disease ? fmtInt(disease.filter((v) => v === 1).length) : 'No disease flags in the data'],
  ];
  return (
    <section className="week-stats" aria-label="This week, all farms">
      <p className="week-stats-title">This week, all farms</p>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

type AreaRow = {
  area: number;
  farms: number;
  reporting: number;
  lice: number | null;
  treated: number | null;
  temp: number | null;
  flagged: number | null;
};
type AreaSummary = { areas: AreaRow[]; all: AreaRow };

/** One week, area by area (south to north) and for the whole coast. */
function areaSummary(data: FarmWeeksYear, at: number, byId: Map<number, Farms[number]>): AreaSummary {
  const by = new Map<number, number[]>();
  data.ids.forEach((id, col) => {
    const a = byId.get(id)?.area;
    if (a === undefined) return;
    by.set(a, [...(by.get(a) ?? []), col]);
  });
  const summarise = (area: number, cols: number[]): AreaRow => {
    const pick = (grid: (number | null)[][] | undefined) => cols.map((c) => grid?.[at]?.[c] ?? null);
    const lice = pick(data.mobile);
    const treated = pick(data.treated).filter((v): v is number => v !== null);
    const disease = data.disease ? pick(data.disease) : null;
    return {
      area,
      farms: cols.length,
      reporting: lice.filter((v) => v !== null).length,
      lice: mean(lice),
      treated: treated.length ? treated.filter((v) => v === 1).length / treated.length : null,
      temp: mean(pick(data.temp)),
      flagged: disease ? disease.filter((v) => v === 1).length : null,
    };
  };
  const areas = [...by.keys()].sort((a, b) => a - b).map((a) => summarise(a, by.get(a)!));
  return { areas, all: summarise(0, data.ids.map((_, c) => c)) };
}

type AreaMeasure = {
  title: string;
  value: (r: AreaRow) => number | null;
  format: (v: number) => string;
  /**
   * Bars start at zero, on a scale that stays put from week to week (it only
   * grows if a value outgrows it), so playing shows real change. Temperature
   * has no true zero, so it's a dot on a fixed 0 to 18 °C line instead.
   */
  kind: 'bar' | 'dot';
  scale: (values: number[]) => number;
  ends?: [string, string];
};

const AREA_MEASURES: Record<LayerKey, AreaMeasure> = {
  lice: { title: 'Mobile lice per fish', value: (r) => r.lice, format: (v) => fmt(v), kind: 'bar', scale: (vs) => Math.max(2, ...vs) },
  temp: { title: 'Sea temperature', value: (r) => r.temp, format: (v) => `${fmt(v, 1)} °C`, kind: 'dot', scale: () => 18, ends: ['0 °C', '18 °C'] },
  treated: { title: 'Reporting farms treated', value: (r) => (r.treated === null ? null : r.treated * 100), format: (v) => `${v.toFixed(0)}%`, kind: 'bar', scale: () => 100 },
  disease: { title: 'Farms flagged for ISA or PD', value: (r) => r.flagged, format: (v) => fmtInt(v), kind: 'bar', scale: (vs) => Math.max(10, ...vs) },
};

/**
 * This week by area for the map's current layer: one row per area, south to
 * north, with its value in text. One neutral colour: length (or position) is
 * the value, so the map's colours keep their one meaning.
 */
function AreaBars({ rows, layer }: { rows: AreaRow[]; layer: LayerKey }) {
  const m = AREA_MEASURES[layer];
  const values = rows.map(m.value);
  const max = m.scale(values.filter((v): v is number => v !== null));
  const pct = (v: number) => Math.min(100, (Math.max(v, 0) / max) * 100);
  return (
    <figure className="area-bars">
      <figcaption>
        <span>{m.title}, by area</span>
        <span className="area-bars-sub">South to north</span>
      </figcaption>
      <ol>
        {rows.map((r, i) => {
          const v = values[i] ?? null;
          const name = AREA_NAMES[r.area] ?? '';
          return (
            <li key={r.area} title={`Area ${r.area}, ${name}: ${v === null ? 'no reports' : m.format(v)}`}>
              <span className="ab-area">{r.area}</span>
              <span className="ab-name">{name}</span>
              <span className={`ab-track ab-track-${m.kind}`} aria-hidden="true">
                {v === null ? null : m.kind === 'dot' ? (
                  <span className="ab-dot" style={{ left: `${pct(v)}%` }} />
                ) : (
                  <span className="ab-bar" style={{ width: `${Math.max(2, pct(v))}%` }} />
                )}
              </span>
              <span className="ab-val">{v === null ? DASH : m.format(v)}</span>
            </li>
          );
        })}
      </ol>
      {m.ends ? (
        <div className="ab-axis" aria-hidden="true">
          <span>{m.ends[0]}</span>
          <span>{m.ends[1]}</span>
        </div>
      ) : null}
    </figure>
  );
}

/** The map's text alternative: this week, area by area. */
function AreaTable({ week, summary }: { week: string; summary: AreaSummary }) {
  const cells = (r: AreaRow) => (
    <>
      <td>
        {fmtInt(r.reporting)} of {fmtInt(r.farms)}
      </td>
      <td>{fmt(r.lice)}</td>
      <td>{r.treated === null ? DASH : `${(r.treated * 100).toFixed(0)}%`}</td>
      <td>{r.temp === null ? DASH : `${fmt(r.temp, 1)} °C`}</td>
      <td>{r.flagged === null ? DASH : fmtInt(r.flagged)}</td>
    </>
  );

  return (
    <Table
      caption={`${weekText(week)}, by production area (south to north)`}
      head={['Area', 'Farms reporting', 'Mobile lice per fish', 'Treated', 'Sea temperature', 'ISA or PD flagged']}
    >
      {summary.areas.map((r) => (
        <tr key={r.area}>
          <th scope="row">
            {r.area} <span className="area-name">{AREA_NAMES[r.area] ?? ''}</span>
          </th>
          {cells(r)}
        </tr>
      ))}
      <tr className="total-row">
        <th scope="row">All areas</th>
        {cells(summary.all)}
      </tr>
    </Table>
  );
}
