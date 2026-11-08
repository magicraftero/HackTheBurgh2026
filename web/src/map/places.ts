// Labels drawn on the farm map, as longitude and latitude.

export type Place = { name: string; lon: number; lat: number };

/** A few cities, so the coast is easy to read; labels sit to the east (inland). */
export const CITIES: Place[] = [
  { name: 'Oslo', lon: 10.7522, lat: 59.9139 },
  { name: 'Bergen', lon: 5.3221, lat: 60.3913 },
  { name: 'Trondheim', lon: 10.3951, lat: 63.4305 },
  { name: 'Bodø', lon: 14.4049, lat: 67.2804 },
  { name: 'Tromsø', lon: 18.956, lat: 69.6496 },
];

export const COUNTRIES: (Place & { main?: boolean })[] = [
  { name: 'NORWAY', lon: 8.9, lat: 61.55, main: true },
  { name: 'SWEDEN', lon: 15.9, lat: 63.1 },
  { name: 'FINLAND', lon: 27.0, lat: 64.5 },
];

export const SEAS: Place[] = [
  { name: 'Norwegian Sea', lon: 5.4, lat: 65.9 },
  { name: 'North Sea', lon: 5.25, lat: 57.55 },
  { name: 'Barents Sea', lon: 26.5, lat: 71.55 },
];

/** Where each production area's number sits: just offshore of its farms. */
export const AREA_SPOTS: Record<number, [number, number]> = {
  1: [8.4, 57.8],
  2: [4.55, 59.15],
  3: [4.15, 60.0],
  4: [3.95, 61.25],
  5: [5.15, 62.85],
  6: [7.25, 64.15],
  7: [9.85, 65.15],
  8: [10.95, 66.6],
  9: [11.9, 68.35],
  10: [15.2, 69.55],
  11: [18.6, 70.4],
  12: [22.6, 71.2],
  13: [30.3, 70.95],
};
