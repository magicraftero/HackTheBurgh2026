/**
 * File access that scripts/run.mjs hands to every script, so the scripts need
 * no Node type packages. Paths are relative to web/. Writes and deletes are
 * only allowed inside the front end's own folders, public/data/_mock/ and
 * public/map/: the back end writes everything else in public/data/ and
 * public/charts/.
 */
export interface IO {
  root: string;
  args: string[];
  read(path: string): string | null;
  list(path: string): string[];
  write(path: string, text: string): void;
  removeDir(path: string): void;
}
