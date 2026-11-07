import { useId, useMemo, useState } from 'react';
import { DASH, fmt, fmtInt, mean } from '../components/format';
import { Later, StatusView } from '../components/States';
import type { Status } from '../data/load';
import type { Farms, FarmWeeksIndex, FarmWeeksYear } from '../data/schemas';
import { useFarmWeeksYear, type Source } from '../data/source';

type Props = { farms: Status<Farms>; index: Status<FarmWeeksIndex>; source: Source };

/** Finding 1: farms.json, farm_weeks/index.json, then one year file at a time. */
export function FarmSection({ farms, index, source }: Props) {
  return (
    <StatusView status={farms} file="farms.json" owner="Data" due="21:30">
      {(farmList) => (
        <>
          <p>
            {fmtInt(farmList.length)} farms in <code>farms.json</code>.
          </p>
          <StatusView status={index} file="farm_weeks/index.json" owner="Data" due="21:30">
            {(idx) => <FarmYears farms={farmList} years={idx.years} source={source} />}
          </StatusView>
        </>
      )}
    </StatusView>
  );
}

function FarmYears({ farms, years, source }: { farms: Farms; years: number[]; source: Source }) {
  const sorted = useMemo(() => [...years].sort((a, b) => a - b), [years]);
  const [year, setYear] = useState<number | null>(sorted[sorted.length - 1] ?? null);
  const status = useFarmWeeksYear(year, source);
  const selectId = useId();

  if (!sorted.length || year === null) {
    return (
      <Later>
        <p>
          <code>farm_weeks/index.json</code> lists no years yet.
        </p>
      </Later>
    );
  }
  return (
    <>
      <p className="control">
        <label htmlFor={selectId}>Year</label>
        <select id={selectId} value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {sorted.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </p>
      {status ? (
        <StatusView status={status} file={`farm_weeks/${year}.json`} owner="Data" due="21:30">
          {(data) => <FarmWeekSummary key={data.year} data={data} farms={farms} />}
        </StatusView>
      ) : null}
    </>
  );
}

/** One year file: pick a week, see what the farms reported that week. */
export function FarmWeekSummary({ data, farms }: { data: FarmWeeksYear; farms: Farms }) {
  const [picked, setPicked] = useState(data.weeks.length - 1);
  const sliderId = useId();
  const unknownIds = useMemo(() => {
    const known = new Set(farms.map((f) => f.id));
    return data.ids.filter((id) => !known.has(id)).length;
  }, [data.ids, farms]);

  if (!data.weeks.length) {
    return (
      <Later>
        <p>
          <code>farm_weeks/{data.year}.json</code> has no weeks yet.
        </p>
      </Later>
    );
  }

  const w = Math.min(Math.max(picked, 0), data.weeks.length - 1);
  const mobile = data.mobile[w] ?? [];
  const treated = (data.treated[w] ?? []).filter((v) => v !== null);
  const disease = data.disease?.[w];
  const reporting = mobile.filter((v) => v !== null).length;
  const treatedShare = treated.length ? treated.filter((v) => v === 1).length / treated.length : null;

  return (
    <div className="farm-week">
      <p>
        {data.year}: {fmtInt(data.weeks.length)} weeks, {fmtInt(data.ids.length)} farms that reported at
        least once.
      </p>
      {unknownIds ? (
        <p className="warn" role="status">
          {fmtInt(unknownIds)} farm IDs in this file aren't in farms.json. Tell Data.
        </p>
      ) : null}
      <p className="control">
        <label htmlFor={sliderId}>
          Week <strong>{data.weeks[w]}</strong>
        </label>
        <input
          id={sliderId}
          type="range"
          min={0}
          max={data.weeks.length - 1}
          step={1}
          value={w}
          aria-valuetext={data.weeks[w]}
          onChange={(e) => setPicked(Number(e.target.value))}
        />
      </p>
      <dl className="stats">
        <div>
          <dt>Farms reporting lice</dt>
          <dd>
            {fmtInt(reporting)} of {fmtInt(data.ids.length)}
          </dd>
        </div>
        <div>
          <dt>Mobile lice per fish</dt>
          <dd>{fmt(mean(mobile))}</dd>
        </div>
        <div>
          <dt>Reporting farms treated</dt>
          <dd>{treatedShare === null ? DASH : `${(treatedShare * 100).toFixed(1)}%`}</dd>
        </div>
        <div>
          <dt>Sea temperature</dt>
          <dd>{fmt(mean(data.temp[w] ?? []))} °C</dd>
        </div>
        <div>
          <dt>Farms flagged ISA or PD</dt>
          <dd>{disease ? fmtInt(disease.filter((v) => v === 1).length) : 'No disease flags in the data'}</dd>
        </div>
      </dl>
      <p className="note">
        Simple averages over the farms that reported, to check the data flow. The analysis itself uses
        capacity-weighted indices.
      </p>
    </div>
  );
}
