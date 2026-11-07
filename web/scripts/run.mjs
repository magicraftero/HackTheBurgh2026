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

const MOCK_DIR = resolve(root, 'public/data/_mock');

function ours(path) {
  const p = resolve(root, path);
  if (p !== MOCK_DIR && !p.startsWith(MOCK_DIR + sep)) {
    throw new Error(`refusing to change ${relative(root, p)}: scripts may only write in public/data/_mock/`);
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
