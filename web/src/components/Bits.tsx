import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { IconCheck, IconClock, IconCross, IconPlus } from './Icons';

// ---- "Show the numbers": a disclosure with a table or stats inside ----

export function Numbers({ title = 'Show the numbers', children }: { title?: string; children: ReactNode }) {
  return (
    <details className="numbers">
      <summary>
        {title}
        <IconPlus size={20} />
      </summary>
      <div className="numbers-body">{children}</div>
    </details>
  );
}

export function Table({ caption, head, children }: { caption: string; head: string[]; children: ReactNode }) {
  return (
    <div className="table-wrap">
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

// ---- Pills: status chips, always icon + label ----

type Tone = 'neutral' | 'good' | 'bad' | 'later' | 'partial' | 'accent' | 'mock' | 'on-dark';

export function Pill({ tone = 'neutral', icon, children }: { tone?: Tone; icon?: ReactNode; children: ReactNode }) {
  return (
    <span className={`pill pill-${tone}`}>
      {icon}
      {children}
    </span>
  );
}

export const PassPill = ({ pass }: { pass: boolean }) =>
  pass ? (
    <Pill tone="good" icon={<IconCheck size={14} />}>
      Pass
    </Pill>
  ) : (
    <Pill tone="bad" icon={<IconCross size={14} />}>
      Fail
    </Pill>
  );

export const LaterPill = ({ children }: { children: ReactNode }) => (
  <Pill tone="later" icon={<IconClock size={14} />}>
    {children}
  </Pill>
);

// ---- Stat tile: label, value, note, optional pill ----

type StatProps = {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  pill?: ReactNode;
  tone?: 'paper' | 'salmon' | 'sky' | 'butter' | 'mint' | 'lilac';
  className?: string;
};

export function StatTile({ label, value, note, pill, tone = 'paper', className = 'stat-tile' }: StatProps) {
  return (
    <div className={`${className} tone-${tone}`}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {note ? <p className="stat-note">{note}</p> : null}
      {pill ? <div className="stat-pill">{pill}</div> : null}
    </div>
  );
}

// ---- Motion helpers (both respect reduced motion) ----

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Counts up from 0 the first time the number scrolls into view. */
export function CountUp({ value, format }: { value: number; format: (n: number) => string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(value);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
      setShown(value);
      return;
    }
    setShown(0);
    let raf = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        const t0 = performance.now();
        const tick = (now: number) => {
          const u = Math.min(1, (now - t0) / 1100);
          setShown(value * (1 - Math.pow(1 - u, 3)));
          if (u < 1) raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value]);

  // Screen readers get the final value, not the animation.
  return (
    <span ref={ref}>
      <span className="sr-only">{format(value)}</span>
      <span aria-hidden="true">{format(shown)}</span>
    </span>
  );
}

/** Fades content up as it scrolls into view. */
export function Reveal({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion() || typeof IntersectionObserver === 'undefined') {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={ref} className={`reveal${inView ? ' is-in' : ''}${className ? ` ${className}` : ''}`}>
      {children}
    </div>
  );
}
