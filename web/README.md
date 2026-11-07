# The site (front end)

A static site that shows the findings. Every number comes from the files the back end writes; nothing is hard-coded. Plan: `docs/plans/frontend.md`. File formats: `docs/plans/00-shared.md`.

**Salmon Signal.** The look takes its feel from Klarna's site (short bold headlines, black pill buttons, soft rounded cards, colour bands), with salmon as the signature colour. It's original: no third-party branding, fonts or images.

**The intro.** A fisherman in a boat; the site hangs on his line under the water. On load he gets a bite, lifts the rod, and the site rises out of the sea. It's driven by scroll position, so scrolling back up rewinds it. "Skip intro" (or any key, click or scroll) stops it, and people with reduced motion switched on start with the site in place. Code: `src/intro/FishingIntro.tsx`.

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
npm run check       # formats, mocks, loader, charts, and the page in every scenario
npm run typecheck
npm run build       # output in dist/
```

## Who writes what

- The back end writes `public/data/*.json`, `public/data/farm_weeks/*.json` and `public/charts/*.vl.json`. Never delete or overwrite those.
- The front end owns everything else in `web/`, including `public/data/_mock/` (regenerate with `npm run mocks`).

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
| `src/intro/FishingIntro.tsx` | The fishing intro |
| `src/page/` | The page: nav, hero, results, findings 1 to 8, footer, data status |
| `src/styles.css` | The design system: colours, type, buttons, pills, cards |
| `scripts/` | Mock generator and checks |

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
