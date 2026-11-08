import type { z } from 'zod';
import {
  AreaMonthSchema,
  ChannelsSchema,
  CombinedSchema,
  DriversSchema,
  FarmerActionsSchema,
  FarmsSchema,
  FarmWeeksIndexSchema,
  NowcastSchema,
  PriceSchema,
  TrapSchema,
} from './schemas';

// Every file the site reads, with its owner and due time (local) from
// docs/plans/00-shared.md. Paths are relative to the site's base path.

export const DATA_FILES = {
  farms: { path: 'data/farms.json', schema: FarmsSchema, owner: 'Data', due: '21:30' },
  farmWeeksIndex: {
    path: 'data/farm_weeks/index.json',
    schema: FarmWeeksIndexSchema,
    owner: 'Data',
    due: '21:30',
  },
  areaMonth: {
    path: 'data/area_month.json',
    schema: AreaMonthSchema,
    owner: 'Production',
    due: '23:30',
  },
  trap: { path: 'data/trap.json', schema: TrapSchema, owner: 'Production', due: '23:30' },
  channels: {
    path: 'data/channels.json',
    schema: ChannelsSchema,
    owner: 'Production',
    due: '01:30 (bins), 04:00 (panel)',
  },
  nowcast: {
    path: 'data/nowcast.json',
    schema: NowcastSchema,
    owner: 'Production',
    due: '01:30 (dev window), 04:00 (holdout)',
  },
  combined: { path: 'data/combined.json', schema: CombinedSchema, owner: 'Production', due: '04:00' },
  farmerActions: { path: 'data/farmer_actions.json', schema: FarmerActionsSchema, owner: 'Production', due: '04:00' },
  drivers: { path: 'data/drivers.json', schema: DriversSchema, owner: 'Production', due: '04:00' },
  price: {
    path: 'data/price.json',
    schema: PriceSchema,
    owner: 'Price',
    due: '03:00 (dev window), 04:00 (holdout)',
  },
} as const;

export type DataKey = keyof typeof DATA_FILES;
export type DataOf<K extends DataKey> = z.infer<(typeof DATA_FILES)[K]['schema']>;

// The site draws its charts from the data files (src/charts/), in one style.
// These two need things only a chart file has, and appear once they're real.
export const CHARTS = {
  price_backtest: { owner: 'Price', due: '04:00' },
  price_fan: { owner: 'Price', due: 'optional' },
} as const;

export type ChartName = keyof typeof CHARTS;

export const chartPath = (name: ChartName) => `charts/${name}.vl.json`;
export const farmWeeksYearPath = (year: number) => `data/farm_weeks/${year}.json`;

export const DATA_KEYS = Object.keys(DATA_FILES) as DataKey[];
export const CHART_NAMES = Object.keys(CHARTS) as ChartName[];
