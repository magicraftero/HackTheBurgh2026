import type { z } from 'zod';

// The result of loading one file. Every state except "ok" means the page shows
// "coming later" for that part only; it never crashes or goes blank.
export type Loaded<T> =
  | { state: 'ok'; url: string; data: T }
  | { state: 'missing'; url: string } // not there yet
  | { state: 'invalid'; url: string; problems: string[] } // there, but doesn't match the contract
  | { state: 'error'; url: string; message: string }; // network or server trouble

export type Status<T> = { state: 'loading' } | Loaded<T>;

const MAX_PROBLEMS = 6;

/**
 * Fetch a JSON file at run time and check it against its schema.
 * Never throws (except when `signal` aborts the request).
 */
export async function loadJson<T>(
  url: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
): Promise<Loaded<T>> {
  let text: string;
  try {
    // "no-cache" revalidates with the server each time, so files that land
    // overnight show up on the next page load instead of hours later.
    const res = await fetch(url, { cache: 'no-cache', signal });
    if (res.status === 404 || res.status === 410) return { state: 'missing', url };
    if (!res.ok) return { state: 'error', url, message: `the server answered ${res.status}` };
    // Dev servers and many hosts answer a missing file with the site's own
    // index.html, so an HTML answer means the file isn't there yet.
    if ((res.headers.get('content-type') ?? '').includes('text/html')) {
      return { state: 'missing', url };
    }
    text = await res.text();
  } catch (e) {
    if (signal?.aborted) throw e;
    return { state: 'error', url, message: e instanceof Error ? e.message : String(e) };
  }
  return parseJson(url, text, schema);
}

/** Parse and check JSON text. Exported for the checks in scripts/. */
export function parseJson<T>(url: string, text: string, schema: z.ZodType<T>): Loaded<T> {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    if (/^\s*</.test(text)) return { state: 'missing', url };
    return {
      state: 'invalid',
      url,
      problems: ['not valid JSON (NaN or Infinity in the file? The contract says to write null)'],
    };
  }
  const parsed = schema.safeParse(raw);
  if (parsed.success) return { state: 'ok', url, data: parsed.data };
  const issues = parsed.error.issues;
  const problems = issues
    .slice(0, MAX_PROBLEMS)
    .map((i) => `${i.path.map(String).join('.') || '(top level)'}: ${i.message}`);
  if (issues.length > MAX_PROBLEMS) problems.push(`…and ${issues.length - MAX_PROBLEMS} more`);
  return { state: 'invalid', url, problems };
}
