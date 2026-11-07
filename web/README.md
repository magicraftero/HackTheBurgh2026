# The site (front end)

A static site that shows the findings. Every number comes from the files the back end writes; nothing is hard-coded. Plan: `docs/plans/frontend.md`. File formats: `docs/plans/00-shared.md`.

**Salmon Signal.** Colours and mood come from the team's "reel-in hero" mockup: navy, coral, misty greys and cream, with serif subtitles. Buttons, pills and cards follow the feel of Klarna's site. It's original: no third-party branding, fonts or images.

**The reel-in hero.** A misty fjord, a fisherman standing in a rowboat, a salmon on his line. "Reel in" (or scrolling) makes him heave the rod; the salmon comes out of the water and the site rises over the scene. It's driven by scroll position, so scrolling back up rewinds it, and any key, click or scroll stops the button's reel-in. People with reduced motion switched on get a still scene and an instant jump. The Oslo card's clock and its "next official figures in N days" (the 20th, per 00-shared.md) are worked out live. Code: `src/intro/FishingIntro.tsx`.

**The farm map (finding 1).** Norway's real coastline with one dot per farm, from `farms.json` and the `farm_weeks/{year}.json` files. Colour the farms by lice, sea temperature, treatments, or ISA and PD (in the key); press play to step through the weeks (it carries on into the next year), or pick a year from the menu beside it; zoom to the south and west, the middle or the north; hover over a farm for its numbers, or click it (or find it by name) for its year week by week next to its area's average. With no farm picked, the week is shown area by area. "This week by area" under the map is the same week as a table. Code: `src/map/` and `src/page/FarmWeeks.tsx`.

- **Fits one screen on a desktop.** "Farms" in the top bar lands on the explorer, which is exactly as tall as the window (at least 520px): the map, then the key, search and the week's numbers, then the chosen farm. Three columns from 1280px wide, two from 1024px; if a column runs long on a short screen, only that column scrolls, never the page or the map. Phones get the same parts stacked. Checked at 1366×650, 1440×790, 1920×950 and 1100×780.

- **No map service.** The coastline is `public/map/norway.json`, a 190 KB (65 KB gzipped) file of SVG paths made once from Natural Earth's 1:10m countries (public domain) by `scripts/make-basemap.ts`, so the map never loads anything from another server and can't break on bad Wi-Fi. It's drawn on two canvases: land underneath, farms on top.
- **Projection.** A transverse Mercator centred on 15°E (the same central meridian as Norway's UTM 33 maps), in `src/map/projection.ts`, shared by the site and the generator so the farms and the coast always line up.
- **Colours.** Each ramp was checked with the dataviz palette validator against the map's night-blue sea: lice is one coral hue in six steps; temperature is blue and coral arms of matching lightness around a grey 8 to 10 °C band (the 9.2 °C average); treated is teal with a ring, and ISA or PD is a red diamond, so neither relies on colour alone. Details at the top of `src/map/scales.ts`.
- **Known limit.** At 1:10m, narrow sounds and small islands are simplified, so about a fifth of farms sit just on land.

To rebuild the coastline (only needed if the projection or view changes):

```sh
mkdir /tmp/wa && cd /tmp/wa && npm pack world-atlas@2.0.2 --ignore-scripts && tar -xzf world-atlas-2.0.2.tgz
cd -  # back to web/
npm run basemap -- /tmp/wa/package/countries-10m.json
```

## Run it

```sh
cd web
npm ci          # installs the exact locked versions; .npmrc blocks install scripts
npm run dev     # http://localhost:5173
```

In development, a bar at the top switches the data:

| URL | Shows |
| --- | --- |
| `/` | The real files in `public/data/` and `public/charts/` |
| `/?mock=pre` | Mock data shaped as before the 04:00 freeze |
| `/?mock=post` | Mock data shaped as after the freeze |
| `/?mock=none` | Every file missing |

Production builds never use mocks: the switch is compiled out, and `public/data/_mock/` is deleted from every build.

## Check it

```sh
npm run check       # formats, mocks, loader, charts, the page in every scenario, and the farm map
npm run check:real  # the real files that have landed: formats, and every chart draws
npm run typecheck
npm run build       # output in dist/
```

## Who writes what

- The back end writes `public/data/*.json`, `public/data/farm_weeks/*.json` and `public/charts/*.vl.json`. Never delete or overwrite those.
- The front end owns everything else in `web/`, including `public/data/_mock/` (regenerate with `npm run mocks`) and `public/map/` (the coastline).

A file shows up on the site once it's pushed to `main` and the host redeploys. The page fetches files at run time, so a missing file never breaks the build. A missing file, or one that doesn't match the agreed format, shows "coming later", and the file table at the top of the page says which and why.

## Hosting (Vercel)

In Vercel: Add New → Project → import the GitHub repo, set **Root Directory** to `web`, and keep the detected Vite settings (build `npm run build`, output `dist`). Every push to `main` then redeploys. If Vercel can't see the repo, the repo owner has to allow Vercel's GitHub app.

The build uses relative paths, so the same `dist/` also works under a sub-path such as GitHub Pages' `/HackTheBurgh2026/`.

## Code map

| Path | What |
| --- | --- |
| `src/data/schemas.ts` | One format check per file, from 00-shared.md |
| `src/data/files.ts` | Every file the site reads, with owner and due time |
| `src/data/load.ts` | Fetch + check, giving ok / missing / invalid / error |
| `src/data/source.ts` | The dev-only mock switch, caching, React hooks |
| `src/components/VegaChart.tsx` | Draws any `.vl.json` chart (vega-embed, responsive, no menu) |
| `src/intro/FishingIntro.tsx` | The reel-in hero |
| `src/map/` | The farm map: projection, coastline loader, colours, canvas map, farm card, search |
| `src/page/` | The page: floating nav, notice, hero, results, findings 1 to 8, footer, data status |
| `src/styles.css` | The design system: colours, type, buttons, pills, cards |
| `scripts/` | Mock generator, coastline generator and checks |

## Chart theme: suggestion for Price (`charts/theme.py`)

The charts are drawn by the back end, so their look lives in Price's theme. These values match the site. The colours passed a colour-blindness check (adjacent pairs, on white). Aqua and yellow sit below 3:1 contrast on white, so every chart has its numbers in a table under "Show the numbers".

```python
PALETTE = {
    "actual": "#2a78d6",                      # observed values: blue
    "drivers": "#eb6834", "c1": "#eb6834",    # our models: salmon orange
    "b1": "#1baf7a", "c0": "#1baf7a",         # main baseline: aqua
    "b0": "#eda100", "ar": "#eda100",         # weaker baseline: yellow
    "rw": "#898781",                          # random walk: grey reference line
    "count": "#e87ba4", "avg_kg": "#008300",  # fish count, average weight
    # Ranked bars (the driver ranking) are one series, so one colour for every group:
    "stock": "#2a78d6", "market": "#2a78d6", "pipeline": "#2a78d6", "feed": "#2a78d6",
    "temperature": "#2a78d6", "losses": "#2a78d6", "lice": "#2a78d6",
}

CONFIG = {
    "font": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    "background": "#ffffff",
    "view": {"stroke": None},
    "title": {"anchor": "start", "fontSize": 18, "fontWeight": 700, "color": "#0b0b0c",
              "subtitleFontSize": 13, "subtitleColor": "#52514e"},
    "axis": {"labelFontSize": 13, "titleFontSize": 13, "titleFontWeight": 600,
             "labelColor": "#52514e", "titleColor": "#52514e",
             "gridColor": "#e1e0d9", "domainColor": "#c3c2b7", "tickColor": "#c3c2b7"},
    "legend": {"labelFontSize": 13, "titleFontSize": 13, "labelColor": "#0b0b0c", "titleColor": "#52514e"},
    "line": {"strokeWidth": 2},
    "point": {"size": 64, "filled": True},
    "bar": {"cornerRadiusEnd": 4},
}
```

Keep titles short and left-aligned (`anchor: start`); long centred titles get cut off on phones.
