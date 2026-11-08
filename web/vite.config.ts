import { cpSync, createReadStream, existsSync, rmSync, statSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig, type Plugin } from 'vite';

// The cockpit is a separate static page (cockpit/ at the repo root). Copy it
// into the build so one Vercel project serves the site at / and the cockpit
// at /cockpit/. In dev, the same path is served straight from that folder.
const cockpitDir = resolve(dirname(fileURLToPath(import.meta.url)), '../cockpit');

const COCKPIT_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
};

function cockpitFile(urlPath: string): string | null {
  const rel = decodeURIComponent(urlPath.slice('/cockpit/'.length));
  const file = resolve(cockpitDir, rel === '' ? 'index.html' : rel);
  const inside = relative(cockpitDir, file);
  if (inside.startsWith('..') || !existsSync(file)) return null;
  if (statSync(file).isDirectory()) {
    const index = join(file, 'index.html');
    return existsSync(index) ? index : null;
  }
  return file;
}

function includeCockpit(): Plugin {
  let outDir = 'dist';
  return {
    name: 'include-cockpit',
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = req.url?.split('?')[0] ?? '';
        if (path !== '/cockpit' && !path.startsWith('/cockpit/')) return next();
        // Relative links in the cockpit (styles.css, data/cockpit.json) only
        // resolve correctly when the page URL ends in a slash.
        if (path === '/cockpit') {
          res.statusCode = 302;
          res.setHeader('Location', '/cockpit/' + (req.url?.includes('?') ? '?' + req.url.split('?')[1] : ''));
          res.end();
          return;
        }
        const file = cockpitFile(path.endsWith('/') ? path + 'index.html' : path);
        if (!file) return next();
        res.setHeader('Content-Type', COCKPIT_TYPES[extname(file)] ?? 'application/octet-stream');
        createReadStream(file).pipe(res);
      });
    },
    closeBundle() {
      cpSync(cockpitDir, join(outDir, 'cockpit'), { recursive: true });
    },
  };
}

// Mock data lives in public/data/_mock/ for development only. Delete it from
// every production build, so it can never be deployed, let alone shown.
function stripMocks(): Plugin {
  let outDir = 'dist';
  return {
    name: 'strip-mocks',
    apply: 'build',
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    closeBundle() {
      rmSync(resolve(outDir, 'data/_mock'), { recursive: true, force: true });
    },
  };
}

export default defineConfig({
  // Relative base: the same build works at a domain root (Vercel) and under a
  // sub-path (GitHub Pages serves /HackTheBurgh2026/). Data files are fetched
  // relative to the page, never from "/".
  base: './',
  plugins: [stripMocks(), includeCockpit()],
  esbuild: { jsx: 'automatic' },
  // Prepare the chart library up front, so the dev server doesn't reload the
  // page the first time a chart appears.
  optimizeDeps: { include: ['vega-embed'] },
  build: {
    target: 'es2022',
    // The chart library is one large file by design; it loads only when the
    // first chart is drawn, so the page itself stays small.
    chunkSizeWarningLimit: 900,
  },
});
