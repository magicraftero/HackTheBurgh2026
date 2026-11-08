import { rmSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig, type Plugin } from 'vite';

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
  plugins: [stripMocks()],
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
