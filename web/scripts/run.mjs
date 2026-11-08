// Runs a TypeScript or TSX script through Vite, so scripts can share the
// site's code and types without extra packages.
//
//   node scripts/run.mjs scripts/make-mocks.ts
//   node scripts/run.mjs scripts/check.tsx
//
// The script's default export receives the IO object below (see scripts/io.ts)
// and returns an exit code.

import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [script, ...args] = process.argv.slice(2);
if (!script) {
  console.error('usage: node scripts/run.mjs <script.ts> [args...]');
  process.exit(2);
}

// The front end's own folders: mock data, and the map outline. The back end
// writes everything else in public/data/ and public/charts/.
const OWN_DIRS = [resolve(root, 'public/data/_mock'), resolve(root, 'public/map')];

function ours(path) {
  const p = resolve(root, path);
  if (!OWN_DIRS.some((dir) => p === dir || p.startsWith(dir + sep))) {
    throw new Error(`refusing to change ${relative(root, p)}: scripts may only write in public/data/_mock/ or public/map/`);
  }
  return p;
}

const io = {
  root,
  args,
  read(path) {
    const p = resolve(root, path);
    return existsSync(p) ? readFileSync(p, 'utf8') : null;
  },
  list(path) {
    const p = resolve(root, path);
    return existsSync(p) ? readdirSync(p) : [];
  },
  write(path, text) {
    const p = ours(path);
    mkdirSync(dirname(p), { recursive: true });
    writeFileSync(p, text);
  },
  removeDir(path) {
    rmSync(ours(path), { recursive: true, force: true });
  },
};

const server = await createServer({
  root,
  configFile: false, // scripts don't need the site's build settings
  esbuild: { jsx: 'automatic' },
  logLevel: 'error',
  appType: 'custom',
  server: { middlewareMode: true, hmr: false, watch: null },
  optimizeDeps: { noDiscovery: true, include: [] },
});

let code = 1;
try {
  const mod = await server.ssrLoadModule('/' + relative(root, resolve(process.cwd(), script)));
  code = (await mod.default(io)) ?? 0;
} catch (e) {
  console.error(e);
} finally {
  await server.close();
}
process.exit(code);
