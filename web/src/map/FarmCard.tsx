import { useId } from 'react';
import { DASH, fmt, fmtInt } from '../components/format';
import { IconCheck, IconClose, IconCross } from '../components/Icons';
import type { Farms, FarmWeeksYear } from '../data/schemas';
import { areaLabel, displayName, weekDates, weekMonth, weekNumber } from './text';

type Farm = Farms[number];
type Series = (number | null)[];

/** Mean of the non-null values in each week, over the given columns. */
export function weeklyMean(grid: Series[], cols: number[]): Series {
  return grid.map((row) => {
    let s = 0;
    let n = 0;
    for (const c of cols) {
      const v = row[c];
      if (v !== null && v !== undefined) {
        s += v;
        n++;
      }
    }
    return n ? s / n : null;
  });
}

const column = (grid: Series[] | undefined, col: number): Series => (grid ? grid.map((row) => row[col] ?? null) : []);
const present = (s: Series) => s.filter((v): v is number => v !== null);

type CardProps = {
  farm: Farm;
  data: FarmWeeksYear;
  /** The farm's column in this year's file, or null if it sent no reports. */
  col: number | null;
  week: number;
  areaCols: number[];
  onWeek: (i: number) => void;
  onClose: () => void;
};

/** One farm, week by week through the year, next to its area's average. */
export function FarmCard({ farm, data, col, week, areaCols, onWeek, onClose }: CardProps) {
  const titleId = useId();
  const name = displayName(farm.name);
  const weeks = data.weeks;
  const at = weeks[week] ?? '';

  return (
    <section className="farm-card" aria-labelledby={titleId}>
      <header className="farm-card-head">
        <div>
          <h3 id={titleId}>{name}</h3>
          <p className="farm-card-meta">
            Site {farm.id} · {areaLabel(farm.area)}
          </p>
          <p className="farm-card-meta">
            {farm.capacity_t !== null ? `Licensed for ${fmtInt(farm.capacity_t)} tonnes of fish` : 'Licensed capacity not listed'}
          </p>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label={`Close ${name}`}>
          <IconClose size={18} />
        </button>
      </header>

      {col === null ? (
        <p className="farm-card-empty">
          {name} sent no lice reports in {data.year}, so it isn't on this year's map.
        </p>
      ) : (
        <CardBody data={data} col={col} week={week} at={at} areaCols={areaCols} onWeek={onWeek} />
      )}
    </section>
  );
}

function CardBody({ data, col, week, at, areaCols, onWeek }: { data: FarmWeeksYear; col: number; week: number; at: string; areaCols: number[]; onWeek: (i: number) => void }) {
  const lice = column(data.mobile, col);
  const temp = column(data.temp, col);
  const treated = column(data.treated, col);
  const disease = data.disease ? column(data.disease, col) : null;
  const areaLice = weeklyMean(data.mobile, areaCols);
  const areaTemp = weeklyMean(data.temp, areaCols);

  const liceNow = lice[week] ?? null;
  const tempNow = temp[week] ?? null;
  const treatedNow = treated[week] ?? null;
  const diseaseNow = disease ? (disease[week] ?? null) : null;
  const reported = present(treated).length;
  const treatedWeeks = present(treated).filter((v) => v === 1).length;
  const flaggedWeeks = disease ? present(disease).filter((v) => v === 1).length : 0;
  const liceMax = Math.max(0, ...present(lice));
  const temps = present(temp);

  return (
    <>
      <dl className="farm-now">
        <div>
          <dt>Lice, week {weekNumber(at)}</dt>
          <dd>{liceNow === null ? 'No count' : `${fmt(liceNow)} per fish`}</dd>
        </div>
        <div>
          <dt>Sea temperature</dt>
          <dd>{tempNow === null ? DASH : `${fmt(tempNow, 1)} °C`}</dd>
        </div>
        <div>
          <dt>Treated</dt>
          <dd>{treatedNow === null ? DASH : treatedNow === 1 ? <Yes>Yes</Yes> : <No>No</No>}</dd>
        </div>
        <div>
          <dt>ISA or PD</dt>
          <dd>{!disease ? 'No flags in data' : diseaseNow === null ? DASH : diseaseNow === 1 ? <Yes alert>Flagged</Yes> : <No>No</No>}</dd>
        </div>
      </dl>

      <p className="farm-card-sub">{data.year}, week by week. Click a week to see it on the map.</p>
      <Spark
        title="Mobile lice per fish"
        summary={present(lice).length ? `Peak ${fmt(liceMax)}` : 'No counts'}
        weeks={data.weeks}
        week={week}
        onWeek={onWeek}
        kind="bars"
        values={lice}
        compare={areaLice}
        format={(v) => `${fmt(v)} lice per fish`}
      />
      <Spark
        title="Sea temperature"
        summary={temps.length ? `${fmt(Math.min(...temps), 1)} to ${fmt(Math.max(...temps), 1)} °C` : 'No readings'}
        weeks={data.weeks}
        week={week}
        onWeek={onWeek}
        kind="line"
        values={temp}
        compare={areaTemp}
        format={(v) => `${fmt(v, 1)} °C`}
      />
      <Spark
        title="Treated for lice"
        summary={reported ? `${treatedWeeks} of ${reported} weeks` : 'No reports'}
        weeks={data.weeks}
        week={week}
        onWeek={onWeek}
        kind="ticks"
        values={treated}
        format={(v) => (v === 1 ? 'treated' : 'not treated')}
      />
      {disease ? (
        <Spark
          title="Flagged for ISA or PD"
          summary={flaggedWeeks ? `${flaggedWeeks} weeks` : 'Not this year'}
          weeks={data.weeks}
          week={week}
          onWeek={onWeek}
          kind="band"
          values={disease}
          format={(v) => (v === 1 ? 'flagged' : 'not flagged')}
        />
      ) : null}
      <p className="spark-legend">
        <span className="spark-key spark-key-farm" aria-hidden="true" /> This farm
        <span className="spark-key spark-key-area" aria-hidden="true" /> Average of its area
      </p>
    </>
  );
}

const Yes = ({ children, alert = false }: { children: string; alert?: boolean }) => (
  <span className={`yn ${alert ? 'yn-alert' : 'yn-yes'}`}>
    <IconCheck size={14} />
    {children}
  </span>
);
const No = ({ children }: { children: string }) => (
  <span className="yn yn-no">
    <IconCross size={14} />
    {children}
  </span>
);

const W = 300;
const H = 46;

type SparkProps = {
  title: string;
  summary: string;
  weeks: string[];
  week: number;
  onWeek: (i: number) => void;
  kind: 'bars' | 'line' | 'ticks' | 'band';
  values: Series;
  compare?: Series;
  format: (v: number) => string;
};

/** A one-year strip chart. Each week is a click target that moves the map to it. */
function Spark({ title, summary, weeks, week, onWeek, kind, values, compare, format }: SparkProps) {
  const n = Math.max(weeks.length, 1);
  const step = W / n;
  const nums = [...present(values), ...(compare ? present(compare) : [])];
  const lo = kind === 'line' ? Math.min(...nums) : 0;
  const hi = kind === 'line' ? Math.max(...nums) : Math.max(...nums, kind === 'bars' ? 0.5 : 1);
  const y = (v: number) => H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 8);
  const line = (s: Series) => {
    let d = '';
    let pen = false;
    s.forEach((v, i) => {
      if (v === null) {
        pen = false;
        return;
      }
      d += `${pen ? 'L' : 'M'}${(i * step + step / 2).toFixed(1)} ${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const months = [0, Math.floor(n / 4), Math.floor(n / 2), Math.floor((3 * n) / 4)].filter((i, k, a) => a.indexOf(i) === k && weeks[i]);

  return (
    <figure className="spark">
      <figcaption>
        <span>{title}</span>
        <span className="spark-summary">{summary}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="presentation">
        <line x1="0" x2={W} y1={H - 2.5} y2={H - 2.5} className="spark-base" />
        {kind === 'bars'
          ? values.map((v, i) =>
              v === null ? null : (
                <rect key={i} className="spark-bar" x={i * step + 0.6} width={Math.max(step - 1.2, 0.8)} y={y(v)} height={Math.max(H - 2.5 - y(v), 0.8)} />
              ),
            )
          : null}
        {kind === 'ticks'
          ? values.map((v, i) => (v === 1 ? <rect key={i} className="spark-tick" x={i * step + step * 0.2} width={step * 0.6} y={6} height={H - 8.5} /> : null))
          : null}
        {kind === 'band'
          ? values.map((v, i) => (v === 1 ? <rect key={i} className="spark-band" x={i * step} width={step + 0.3} y={6} height={H - 8.5} /> : null))
          : null}
        {compare ? <path d={line(compare)} className="spark-area" vectorEffect="non-scaling-stroke" /> : null}
        {kind === 'line' ? <path d={line(values)} className="spark-line" vectorEffect="non-scaling-stroke" /> : null}
        <line x1={week * step + step / 2} x2={week * step + step / 2} y1="0" y2={H} className="spark-now" vectorEffect="non-scaling-stroke" />
        {weeks.map((w, i) => (
          <rect key={w} x={i * step} width={step} y="0" height={H} className="spark-hit" onClick={() => onWeek(i)}>
            <title>{`Week ${weekNumber(w)}: ${values[i] === null || values[i] === undefined ? 'no report' : format(values[i]!)}`}</title>
          </rect>
        ))}
      </svg>
      <div className="spark-axis" aria-hidden="true">
        {months.map((i) => (
          <span key={i} style={{ left: `${(i / n) * 100}%` }}>
            {weekMonth(weeks[i]!)}
          </span>
        ))}
      </div>
      <p className="sr-only">
        {title}, {weekDates(weeks[week] ?? '')}: {values[week] === null || values[week] === undefined ? 'no report' : format(values[week]!)}.
      </p>
    </figure>
  );
}
