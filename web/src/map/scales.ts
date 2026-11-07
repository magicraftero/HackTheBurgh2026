// Colours, bins and marks for the farm map's four layers.
//
// The map is drawn on a night-blue sea (MAP.sea). Every ramp was checked with
// the dataviz palette validator against that surface (ordinal mode, dark):
// - lice: one coral hue, six steps with even lightness gaps (OKLCH L .52 to .92),
//   darkest step 2.8:1 against the sea;
// - temperature: diverging, a blue arm and a coral arm with matching lightness
//   (L .60, .70, .83) around a neutral grey for the 8–10 °C band, which holds the
//   9.2 °C average of every farm-week since 2019;
// - treatments and disease: emphasis (one colour, everything else grey), and
//   always a second channel: a ring for treated, a diamond for ISA or PD.
//   Treated is teal so its ring never reads as the palest lice step (deutan
//   ΔE 14.6 from the middle of the lice ramp; 9:1 against the sea).
// Legend and label text never wears these colours.

export const MAP = {
  sea: '#142130',
  norway: '#2b4157',
  neighbours: '#1c2d3f',
  coast: '#5d7891',
  border: '#7d93a8',
  label: '#c7d0d9',
  labelSoft: '#8fa2b5',
  ring: '#5cd5c7',
} as const;

export type LayerKey = 'lice' | 'temp' | 'treated' | 'disease';

export type Values = {
  mobile: number | null;
  temp: number | null;
  treated: number | null;
  disease: number | null;
};

export type Shape = 'dot' | 'diamond' | 'empty';
/** How one farm is drawn this week. `rank` sets the drawing order: higher on top. */
export type Mark = { fill: string; shape: Shape; ring: boolean; rank: number };

export const LICE_BREAKS = [0.1, 0.25, 0.5, 1, 2];
export const LICE_COLORS = ['#9d5035', '#c2603d', '#e2754f', '#f29676', '#fcb8a1', '#ffdcd0'];
export const LICE_LABELS = ['Under 0.1', '0.1 to 0.25', '0.25 to 0.5', '0.5 to 1', '1 to 2', '2 or more'];

export const TEMP_BREAKS = [4, 6, 8, 10, 12, 14];
export const TEMP_COLORS = ['#a4ccf3', '#64a4e0', '#3e85c4', '#595b5d', '#c06143', '#e28061', '#f6b6a2'];
export const TEMP_LABELS = ['Under 4 °C', '4 to 6 °C', '6 to 8 °C', '8 to 10 °C', '10 to 12 °C', '12 to 14 °C', '14 °C or more'];
export const TEMP_MIDDLE = 9;

export const PLAIN = '#5d646c';
export const TREATED = MAP.ring;
export const FLAGGED = '#ef6661';
export const NO_REPORT = '#576574';

/** Index of the bin `v` falls in: below the first break is 0. */
export function binIndex(v: number, breaks: number[]): number {
  let i = 0;
  while (i < breaks.length && v >= breaks[i]!) i++;
  return i;
}

const EMPTY: Mark = { fill: NO_REPORT, shape: 'empty', ring: false, rank: -1 };

export function markFor(layer: LayerKey, v: Values): Mark {
  switch (layer) {
    case 'lice':
      if (v.mobile === null) return EMPTY;
      return { fill: LICE_COLORS[binIndex(v.mobile, LICE_BREAKS)]!, shape: 'dot', ring: v.treated === 1, rank: v.mobile };
    case 'temp':
      if (v.temp === null) return EMPTY;
      return { fill: TEMP_COLORS[binIndex(v.temp, TEMP_BREAKS)]!, shape: 'dot', ring: false, rank: Math.abs(v.temp - TEMP_MIDDLE) };
    case 'treated':
      if (v.treated === null) return EMPTY;
      return v.treated === 1
        ? { fill: TREATED, shape: 'dot', ring: true, rank: 2 }
        : { fill: PLAIN, shape: 'dot', ring: false, rank: 1 };
    case 'disease':
      if (v.disease === null) return EMPTY;
      return v.disease === 1
        ? { fill: FLAGGED, shape: 'diamond', ring: false, rank: 2 }
        : { fill: PLAIN, shape: 'dot', ring: false, rank: 1 };
  }
}

export type LegendItem = { mark: Mark; label: string };
/** A binned colour scale, shown in the key as one bar with the breaks under it. */
export type Ramp = { colors: string[]; breaks: number[]; labels: string[]; ends?: [string, string] };
export type LayerInfo = { key: LayerKey; label: string; title: string; note?: string; ramp?: Ramp; items: LegendItem[] };

const dot = (fill: string, ring = false): Mark => ({ fill, shape: 'dot', ring, rank: 0 });

export const LAYERS: LayerInfo[] = [
  {
    key: 'lice',
    label: 'Lice',
    title: 'Mobile lice per fish',
    note: 'Each farm counts the lice on a sample of its fish every week.',
    ramp: { colors: LICE_COLORS, breaks: LICE_BREAKS, labels: LICE_LABELS, ends: ['Fewer', 'More'] },
    items: [
      { mark: dot(LICE_COLORS[2]!, true), label: 'Ring: treated this week' },
      { mark: EMPTY, label: 'No count this week' },
    ],
  },
  {
    key: 'temp',
    label: 'Sea temperature',
    title: 'Sea temperature, °C',
    note: `Grey is about average: farm-weeks since 2019 average ${TEMP_MIDDLE}.2 °C.`,
    ramp: { colors: TEMP_COLORS, breaks: TEMP_BREAKS, labels: TEMP_LABELS, ends: ['Colder', 'Warmer'] },
    items: [{ mark: EMPTY, label: 'No reading this week' }],
  },
  {
    key: 'treated',
    label: 'Treatments',
    title: 'Treated for lice this week',
    note: 'Any delousing that week, with medicines or without (for example warm or fresh water).',
    items: [
      { mark: { fill: TREATED, shape: 'dot', ring: true, rank: 0 }, label: 'Treated this week' },
      { mark: dot(PLAIN), label: 'No treatment' },
      { mark: EMPTY, label: 'No report this week' },
    ],
  },
  {
    key: 'disease',
    label: 'ISA and PD',
    title: 'Flagged for ISA or PD',
    note: 'Suspected or confirmed infectious salmon anaemia or pancreas disease.',
    items: [
      { mark: { fill: FLAGGED, shape: 'diamond', ring: false, rank: 0 }, label: 'Flagged this week' },
      { mark: dot(PLAIN), label: 'Not flagged' },
      { mark: EMPTY, label: 'No status this week' },
    ],
  },
];

export const layerInfo = (key: LayerKey): LayerInfo => LAYERS.find((l) => l.key === key)!;
