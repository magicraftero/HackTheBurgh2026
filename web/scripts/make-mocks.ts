// Writes the mock findings into public/data/_mock/{pre,post}/.
// Run with: npm run mocks
import type { IO } from './io';
import { buildScenario } from './mock-data';

const OUT = 'public/data/_mock';

const README = `# Mock findings (front end, development only)

Made-up, schema-correct copies of every file in docs/plans/00-shared.md, for
building and testing the site before the real findings land.

- \`pre/\`: the shapes before the 04:00 freeze (no holdout, no F1/F2, no panel, no drivers.json).
- \`post/\`: the shapes after the freeze.
- \`?mock=none\` in the dev server simulates every file missing.

Open the dev server with \`?mock=pre\`, \`?mock=post\` or \`?mock=none\`. Production
builds never read these files: vite.config.ts deletes this folder from every build.

Regenerate with \`npm run mocks\` (from web/). Don't edit by hand.
`;

export default function main(io: IO): number {
  for (const scenario of ['pre', 'post'] as const) {
    io.removeDir(`${OUT}/${scenario}`);
    const files = buildScenario(scenario);
    for (const [path, value] of Object.entries(files)) {
      io.write(`${OUT}/${scenario}/${path}`, JSON.stringify(value) + '\n');
    }
    console.log(`${scenario}: wrote ${Object.keys(files).length} files`);
  }
  io.write(`${OUT}/README.md`, README);
  return 0;
}
