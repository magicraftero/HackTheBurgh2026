// Words for the farm map: ISO weeks as dates, farm and area names, search.

/** The official names of Norway's 13 production areas for salmon and trout. */
export const AREA_NAMES: Record<number, string> = {
  1: 'Svenskegrensen til Jæren',
  2: 'Ryfylke',
  3: 'Karmøy til Sotra',
  4: 'Nordhordland til Stadt',
  5: 'Stadt til Hustadvika',
  6: 'Nordmøre og Sør-Trøndelag',
  7: 'Nord-Trøndelag med Bindal',
  8: 'Helgeland til Bodø',
  9: 'Vestfjorden og Vesterålen',
  10: 'Andøya til Senja',
  11: 'Kvaløya til Loppa',
  12: 'Vest-Finnmark',
  13: 'Øst-Finnmark',
};

export const areaLabel = (area: number) => `Area ${area}${AREA_NAMES[area] ? `, ${AREA_NAMES[area]}` : ''}`;

const WEEK = /^(\d{4})-W(\d{2})$/;

/** "2026-W44" → 44. */
export function weekNumber(week: string): number {
  const m = WEEK.exec(week);
  return m ? Number(m[2]) : NaN;
}

/** Monday and Sunday of an ISO week (UTC dates). Week 1 is the week with 4 January in it. */
export function isoWeekDays(week: string): { monday: Date; sunday: Date } | null {
  const m = WEEK.exec(week);
  if (!m) return null;
  const year = Number(m[1]);
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const fromMonday = (jan4.getUTCDay() + 6) % 7;
  const monday = new Date(jan4.getTime() + ((Number(m[2]) - 1) * 7 - fromMonday) * 86_400_000);
  return { monday, sunday: new Date(monday.getTime() + 6 * 86_400_000) };
}

const day = (d: Date, opts: Intl.DateTimeFormatOptions) => d.toLocaleDateString('en-GB', { ...opts, timeZone: 'UTC' });

/** "2026-W44" → "26 Oct to 1 Nov 2026"; "2025-W41" → "6 to 12 Oct 2025". */
export function weekDates(week: string): string {
  const d = isoWeekDays(week);
  if (!d) return week;
  const { monday: a, sunday: b } = d;
  if (a.getUTCFullYear() !== b.getUTCFullYear()) {
    return `${day(a, { day: 'numeric', month: 'short', year: 'numeric' })} to ${day(b, { day: 'numeric', month: 'short', year: 'numeric' })}`;
  }
  if (a.getUTCMonth() !== b.getUTCMonth()) {
    return `${day(a, { day: 'numeric', month: 'short' })} to ${day(b, { day: 'numeric', month: 'short', year: 'numeric' })}`;
  }
  return `${a.getUTCDate()} to ${day(b, { day: 'numeric', month: 'short', year: 'numeric' })}`;
}

/**
 * Short month for chart axes, from the week's Thursday (an ISO week belongs to
 * the year its Thursday is in): "2026-W01" → "Jan", although it starts 29 Dec.
 */
export const weekMonth = (week: string) => {
  const d = isoWeekDays(week);
  return d ? day(new Date(d.monday.getTime() + 3 * 86_400_000), { month: 'short' }) : '';
};

/**
 * The register spells many names in capitals ("REVØY"). Show those in title
 * case ("Revøy"), keeping single letters and Roman numerals ("Finnkjerka S",
 * "Hågardsneset II"). Names already in mixed case are left alone.
 */
export function displayName(name: string): string {
  const trimmed = name.trim();
  if (trimmed !== trimmed.toLocaleUpperCase('nb-NO') || !/\p{L}{2}/u.test(trimmed)) return trimmed;
  return trimmed
    .toLocaleLowerCase('nb-NO')
    .replace(/[\p{L}\p{N}]+/gu, (w) => {
      if (w.length === 1 || /^[ivx]+$/.test(w)) return w.toLocaleUpperCase('nb-NO');
      return w[0]!.toLocaleUpperCase('nb-NO') + w.slice(1);
    });
}

/** A loose key for search: lower case, accents off, ø→o, æ→ae, å→a. */
export function searchKey(s: string): string {
  return s
    .toLocaleLowerCase('nb-NO')
    .replace(/æ/g, 'ae')
    .replace(/ø/g, 'o')
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}
