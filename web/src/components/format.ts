// Number formatting. Every helper shows "—" for a missing (null) value.

export const DASH = '—';

type N = number | null | undefined;

export const fmt = (v: N, digits = 2) =>
  v == null
    ? DASH
    : v.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const fmtInt = (v: N) => (v == null ? DASH : Math.round(v).toLocaleString('en-GB'));

/** Signed percentage, e.g. "+11.8%" or "−2.2%". */
export const fmtPct = (v: N, digits = 1) =>
  v == null ? DASH : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(digits)}%`;

/** Kilograms shown as tonnes. */
export const fmtTonnes = (kg: N) => (kg == null ? DASH : `${fmtInt(kg / 1000)} t`);

export const fmtP = (p: N) => (p == null ? DASH : p < 0.001 ? '< 0.001' : p.toFixed(3));

export const fmtR = (r: N) => (r == null ? DASH : `${r < 0 ? '−' : ''}${Math.abs(r).toFixed(2)}`);

const compact = new Intl.NumberFormat('en-GB', { notation: 'compact', maximumFractionDigits: 1 });

/** 1,284 → "1.3K", 4,200,000 → "4.2M"; small numbers stay whole. */
export const fmtCompact = (v: N) => (v == null ? DASH : Math.abs(v) < 10_000 ? fmtInt(v) : compact.format(v));

/** "2026-09" → "September 2026". */
export function fmtMonth(month: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(month);
  if (!m) return month;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, 1)).toLocaleString('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

/** "2026-10-10" → "10 Oct 2026". */
export function fmtDate(day: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (!m) return day;
  return new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export const mean = (xs: readonly (number | null)[]) => {
  let sum = 0;
  let n = 0;
  for (const x of xs) {
    if (x != null) {
      sum += x;
      n += 1;
    }
  }
  return n ? sum / n : null;
};
