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
