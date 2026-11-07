# The site (front end)

A static site that shows the findings. Every number comes from the files the back end writes; nothing is hard-coded. Plan: `docs/plans/frontend.md`. File formats: `docs/plans/00-shared.md`.

This is the Phase 0 foundation: a plain test page with every finding under its title. The team's design gets built on top of it.

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
| `src/page/` | The test page: file table and findings 1 to 8 |
| `scripts/` | Mock generator and checks |
