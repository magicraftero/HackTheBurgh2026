import { useId, useMemo, useState } from 'react';
import { IconSearch } from '../components/Icons';
import type { Farms } from '../data/schemas';
import { displayName, searchKey } from './text';

type Option = { id: number; name: string; area: number; key: string; reports: boolean };

const MAX_OPTIONS = 8;

/**
 * Find a farm by name or site number. A combobox: type, then pick with the
 * arrow keys and Enter, or click. Farms that sent no reports in the year are
 * still listed, and say so.
 */
export function FarmSearch({
  farms,
  reporting,
  year,
  onPick,
}: {
  farms: Farms;
  reporting: Set<number>;
  year: number;
  onPick: (id: number) => void;
}) {
  const id = useId();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const all = useMemo<Option[]>(
    () =>
      farms
        .filter((f) => f.lat !== null && f.lon !== null)
        .map((f) => ({ id: f.id, name: displayName(f.name), area: f.area, key: searchKey(f.name), reports: false })),
    [farms],
  );

  const options = useMemo(() => {
    const q = searchKey(query);
    if (!q) return [];
    const starts: Option[] = [];
    const words: Option[] = [];
    const inside: Option[] = [];
    for (const o of all) {
      if (o.key.startsWith(q) || String(o.id) === q) starts.push(o);
      else if (o.key.includes(` ${q}`)) words.push(o);
      else if (o.key.includes(q)) inside.push(o);
    }
    const byReports = (a: Option, b: Option) => Number(reporting.has(b.id)) - Number(reporting.has(a.id)) || a.name.localeCompare(b.name, 'nb');
    return [...starts.sort(byReports), ...words.sort(byReports), ...inside.sort(byReports)]
      .slice(0, MAX_OPTIONS)
      .map((o) => ({ ...o, reports: reporting.has(o.id) }));
  }, [all, query, reporting]);

  const shown = open && options.length > 0;
  const pick = (o: Option) => {
    onPick(o.id);
    setQuery(o.name);
    setOpen(false);
  };

  return (
    <div className="farm-search">
      <label htmlFor={`${id}-input`} className="sr-only">
        Find a farm
      </label>
      <div className="farm-search-box">
        <IconSearch size={18} />
        <input
          id={`${id}-input`}
          type="search"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          placeholder="Find a farm by name or site number"
          aria-expanded={shown}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={shown ? `${id}-opt-${active}` : undefined}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown' && options.length) {
              e.preventDefault();
              setOpen(true);
              setActive((a) => (a + 1) % options.length);
            } else if (e.key === 'ArrowUp' && options.length) {
              e.preventDefault();
              setActive((a) => (a - 1 + options.length) % options.length);
            } else if (e.key === 'Enter' && shown) {
              e.preventDefault();
              pick(options[Math.min(active, options.length - 1)]!);
            } else if (e.key === 'Escape') {
              setOpen(false);
            }
          }}
        />
      </div>
      <ul id={`${id}-list`} role="listbox" aria-label="Matching farms" className="farm-search-list" hidden={!shown}>
        {options.map((o, i) => (
          <li
            key={o.id}
            id={`${id}-opt-${i}`}
            role="option"
            aria-selected={i === active}
            className={i === active ? 'is-active' : undefined}
            // mousedown, not click: it has to land before the input's blur closes the list
            onMouseDown={(e) => {
              e.preventDefault();
              pick(o);
            }}
            onMouseEnter={() => setActive(i)}
          >
            <span className="farm-search-name">{o.name}</span>
            <span className="farm-search-meta">
              Area {o.area}
              {o.reports ? '' : ` · no reports in ${year}`}
            </span>
          </li>
        ))}
      </ul>
      {open && searchKey(query) && !options.length ? (
        <p className="farm-search-none" role="status">
          No farm matches “{query}”.
        </p>
      ) : null}
    </div>
  );
}
