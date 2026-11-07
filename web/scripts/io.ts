/**
 * File access that scripts/run.mjs hands to every script, so the scripts need
 * no Node type packages. Paths are relative to web/. Writes and deletes are
 * only allowed inside public/data/_mock/, the front end's own folder: the
 * back end writes everything else in public/data/ and public/charts/.
 */
export interface IO {
  root: string;
  args: string[];
  read(path: string): string | null;
  list(path: string): string[];
  write(path: string, text: string): void;
  removeDir(path: string): void;
}
