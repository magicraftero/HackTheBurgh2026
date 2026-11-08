/**
 * File names, owners, due times and format problems are notes for the people
 * building the site. They show only on a development build opened with ?debug.
 */
export function showBuildNotes(): boolean {
  return import.meta.env.DEV && typeof location !== 'undefined' && new URLSearchParams(location.search).has('debug');
}
