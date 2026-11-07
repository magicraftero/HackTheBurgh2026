import { useEffect, useRef, useState, type RefObject } from 'react';
import { IconReel } from '../components/Icons';

/*
  The reel-in hero, after the team's mockup: misty fjord, a fisherman standing
  in a rowboat, a salmon on the line. "Reel in" (or scrolling) makes him heave
  the rod; the salmon comes out of the water and the site rises over the scene.

  How it works: the scene is a sticky, full-screen layer behind the site, which
  starts just below the screen. Everything is driven by scroll position, so the
  button simply scrolls the page and scrolling by hand plays (and rewinds) the
  same motion. One rAF loop runs while the scene is visible and stops after.

  Accessibility: the drawing is decorative (aria-hidden); the headline, button
  and card are real content. Any key, wheel or touch stops the reel-in.
  Reduced-motion users get a still scene and an instant jump.
*/

// The drawing's own coordinates (viewBox 0 0 820 520).
const VIEW_W = 820;
const WATERLINE = 392; // where the boat floats
const HANDS = { x: 322, y: 238 }; // the rod pivots in his hands
const ROD_LENGTH = 340;
const ANGLE_REST = -36; // degrees; negative tilts the tip up
const ANGLE_UP = -68;
const FISH_REST = { x: 668, y: 452 }; // the salmon's mouth, at the surface
const REEL_TIME = 2600; // ms for the whole reel-in

export const REPLAY_EVENT = 'salmon-signal:back-to-boat';

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const easeOut = (u: number) => 1 - Math.pow(1 - u, 3);
const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);

/** The rod: its path before rotation, and its tip after rotation (drawing units). */
function rod(deg: number, bend: number) {
  const tip = { x: HANDS.x + ROD_LENGTH, y: HANDS.y + bend };
  const a = (deg * Math.PI) / 180;
  const dx = tip.x - HANDS.x;
  const dy = tip.y - HANDS.y;
  return {
    d: `M${HANDS.x - 26} ${HANDS.y} Q${HANDS.x + ROD_LENGTH * 0.58} ${HANDS.y + bend * 0.12} ${tip.x} ${tip.y}`,
    tip: {
      x: HANDS.x + dx * Math.cos(a) - dy * Math.sin(a),
      y: HANDS.y + dx * Math.sin(a) + dy * Math.cos(a),
    },
  };
}

const DROPLETS = [
  [-30, -46],
  [-14, -64],
  [6, -72],
  [24, -58],
  [40, -40],
  [-46, -20],
  [52, -18],
] as const;

// Reflection lines on the water: [left %, top %, width %, kind].
const GLINTS: [number, number, number, 'light' | 'dark'][] = [
  [8, 14, 12, 'light'],
  [38, 9, 9, 'light'],
  [82, 16, 11, 'light'],
  [5, 34, 10, 'light'],
  [56, 30, 12, 'light'],
  [86, 40, 8, 'light'],
  [20, 52, 14, 'dark'],
  [66, 58, 13, 'light'],
  [2, 72, 16, 'light'],
  [44, 76, 12, 'dark'],
  [74, 84, 15, 'dark'],
  [28, 90, 18, 'dark'],
];

type Props = { siteRef: RefObject<HTMLDivElement | null>; hasCurrentCall: boolean };

export function FishingIntro({ siteRef, hasCurrentCall }: Props) {
  const sceneRef = useRef<HTMLElement>(null);
  const actionRef = useRef<HTMLDivElement>(null);
  const boatRef = useRef<SVGGElement>(null);
  const rodRef = useRef<SVGGElement>(null);
  const rodPathRef = useRef<SVGPathElement>(null);
  const lineRef = useRef<SVGPathElement>(null);
  const fishRef = useRef<SVGGElement>(null);
  const rippleRef = useRef<SVGGElement>(null);
  const splashRef = useRef<SVGGElement>(null);
  const copyRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    const action = actionRef.current;
    const boat = boatRef.current;
    const rodGroup = rodRef.current;
    const rodPath = rodPathRef.current;
    const line = lineRef.current;
    const fish = fishRef.current;
    const ripple = rippleRef.current;
    const splash = splashRef.current;
    const copy = copyRef.current;
    const cta = ctaRef.current;
    const card = cardRef.current;
    const button = buttonRef.current;
    const site = siteRef.current;
    if (!scene || !action || !boat || !rodGroup || !rodPath || !line || !fish || !ripple || !splash || !copy || !cta || !card || !button || !site) {
      return;
    }

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

    let travel = 1; // scroll distance until the site reaches the top
    let actionTop = 0;
    let scale = 1;

    const measure = () => {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const width = vw >= 720 ? clamp(vw * 0.6, 600, 1000) : 560;
      const s = width / VIEW_W;
      const left = vw >= 720 ? (vw - width) / 2 : vw - 50 - FISH_REST.x * s;
      action.style.width = `${width}px`;
      action.style.left = `${left}px`;
      actionTop = vh * 0.8 - WATERLINE * s;
      scale = s;
      action.style.top = `${actionTop}px`;
      travel = Math.max(1, site.getBoundingClientRect().top + window.scrollY);
    };

    // ---- The reel-in: an eased scroll to the site ----
    let reel: { from: number; start: number } | null = null;
    const startReel = () => {
      if (reduce) {
        window.scrollTo(0, travel);
        document.getElementById('top-heading')?.focus({ preventScroll: true });
        return;
      }
      reel = { from: window.scrollY, start: performance.now() };
      wake();
    };
    const stopReel = () => {
      reel = null;
    };
    const backToBoat = () => {
      stopReel();
      window.scrollTo(0, 0);
      wake();
    };

    // ---- One frame ----
    const t0 = performance.now();
    let raf = 0;
    let prevLift = 0;
    let hidden = false;

    const render = (now: number) => {
      const p = clamp(window.scrollY / travel, 0, 1);
      const time = reduce ? 0 : (now - t0) / 1000;

      // Idle life: the boat rocks, and every few seconds the salmon fights.
      const bob = Math.sin(time * 1.6) * 2.2;
      const tug = reduce ? 0 : Math.pow(Math.max(0, Math.sin(time * 1.4)), 16);
      boat.setAttribute('transform', `translate(0 ${bob.toFixed(2)})`);

      // He heaves the rod as the site rises.
      const heave = easeOut(clamp(p / 0.32, 0, 1));
      const deg = lerp(ANGLE_REST, ANGLE_UP, heave);
      const bend = 26 + 22 * Math.sin(Math.PI * clamp(p / 0.4, 0, 1)) + 10 * tug;
      const shape = rod(deg, bend);
      rodGroup.setAttribute('transform', `rotate(${deg.toFixed(2)} ${HANDS.x} ${HANDS.y})`);
      rodPath.setAttribute('d', shape.d);
      const tipX = shape.tip.x;
      const tipY = shape.tip.y + bob;

      // The salmon comes out of the water and up to the rod.
      const lift = easeInOut(clamp(p / 0.36, 0, 1));
      const fx = lerp(FISH_REST.x, tipX + 14, lift);
      const fy = lerp(FISH_REST.y - 3 * tug, tipY + 78, lift);
      const fight = Math.sin(time * 8) * (2 + 9 * tug) * (1 - 0.6 * lift);
      fish.setAttribute('transform', `translate(${fx.toFixed(1)} ${fy.toFixed(1)}) rotate(${(lerp(26, 84, lift) + fight).toFixed(2)})`);

      const sag = 10 * (1 - lift);
      line.setAttribute(
        'd',
        `M${tipX.toFixed(1)} ${tipY.toFixed(1)} Q${((tipX + fx) / 2 + sag).toFixed(1)} ${((tipY + fy) / 2).toFixed(1)} ${fx.toFixed(1)} ${fy.toFixed(1)}`,
      );

      // Once the site rises past his head, the rod and the catch fade with him.
      const headY = actionTop + 170 * scale;
      const catchFade = clamp((site.getBoundingClientRect().top - headY + 40) / 120, 0, 1).toFixed(3);
      rodGroup.style.opacity = catchFade;
      line.style.opacity = catchFade;
      fish.style.opacity = catchFade;

      ripple.style.opacity = lift < 0.05 ? '1' : '0';
      if (prevLift < 0.1 && lift >= 0.1 && !reduce) {
        splash.classList.remove('go');
        void splash.getBoundingClientRect(); // restart the animation
        splash.classList.add('go');
      }
      prevLift = lift;

      // The words make way.
      const fadeCopy = clamp(p / 0.25, 0, 1);
      copy.style.opacity = (1 - fadeCopy).toFixed(3);
      copy.style.transform = `translate(-50%, ${(-40 * fadeCopy).toFixed(1)}px)`;
      const fadeUi = (1 - clamp(p / 0.1, 0, 1)).toFixed(3);
      cta.style.opacity = fadeUi;
      card.style.opacity = fadeUi;
      cta.style.visibility = p > 0.12 ? 'hidden' : 'visible';

      site.style.setProperty('--panel-r', `${(32 * (1 - clamp((p - 0.88) / 0.12, 0, 1))).toFixed(1)}px`);

      // Once the site covers the screen, hide the scene so it costs nothing.
      const covered = p >= 1 && !reel;
      if (covered !== hidden) {
        hidden = covered;
        scene.style.visibility = covered ? 'hidden' : 'visible';
      }
      return covered;
    };

    const loop = (now: number) => {
      raf = 0;
      if (reel) {
        const u = clamp((now - reel.start) / REEL_TIME, 0, 1);
        window.scrollTo(0, lerp(reel.from, travel, easeInOut(u)));
        if (u >= 1) {
          reel = null;
          document.getElementById('top-heading')?.focus({ preventScroll: true });
        }
      }
      if (!render(now) || reel) raf = requestAnimationFrame(loop);
    };
    function wake() {
      if (!raf) raf = requestAnimationFrame(loop);
    }

    // ---- Wiring ----
    const onResize = () => {
      measure();
      wake();
    };
    const onUserInput = (e: Event) => {
      if (e instanceof KeyboardEvent && (e.key === 'Tab' || e.key === 'Shift')) return;
      stopReel();
    };
    const inputs = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;

    measure();
    window.addEventListener('scroll', wake, { passive: true });
    window.addEventListener('resize', onResize);
    window.addEventListener(REPLAY_EVENT, backToBoat);
    for (const name of inputs) window.addEventListener(name, onUserInput, { passive: true });
    button.addEventListener('click', startReel);

    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (target) requestAnimationFrame(() => target.scrollIntoView());
    else window.scrollTo(0, 0);
    wake();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', wake);
      window.removeEventListener('resize', onResize);
      window.removeEventListener(REPLAY_EVENT, backToBoat);
      for (const name of inputs) window.removeEventListener(name, onUserInput);
      button.removeEventListener('click', startReel);
    };
  }, [siteRef]);

  const rest = rod(ANGLE_REST, 26);

  return (
    <section className="intro" id="intro" ref={sceneRef} aria-labelledby="intro-title">
      <div className="intro-art" aria-hidden="true">
        <div className="intro-sun" />
        <svg className="intro-hills" viewBox="0 0 1600 150" preserveAspectRatio="none">
          <path d="M0 150V92c180-32 360-8 540-22 200-16 360 18 560-4 200-20 360 10 500-6v90z" fill="#cfd3d1" />
          <path d="M0 150v-32c220-22 420-4 660-16 220-10 400 14 620-2 150-10 250 6 320-2v52z" fill="#bcc3c4" />
        </svg>
        <svg className="intro-mountain left" viewBox="0 0 760 470" preserveAspectRatio="xMinYMax meet">
          <defs>
            <pattern id="rain-left" width="34" height="58" patternUnits="userSpaceOnUse" patternTransform="rotate(16)">
              <line x1="6" y1="4" x2="6" y2="40" stroke="#7a8691" strokeWidth="1.6" strokeLinecap="round" />
            </pattern>
          </defs>
          <path d="M0 470V60c30-30 90-52 130-46 40 6 75 46 110 86 80 90 180 190 280 260 70 50 150 90 240 110z" fill="#5c6876" />
          <path d="M0 470V60c30-30 90-52 130-46 40 6 75 46 110 86 80 90 180 190 280 260 70 50 150 90 240 110z" fill="url(#rain-left)" />
          <path d="M0 470V250c70-14 150 0 230 50 70 44 140 110 210 170z" fill="#2d3946" />
        </svg>
        <svg className="intro-mountain right" viewBox="0 0 520 430" preserveAspectRatio="xMaxYMax meet">
          <defs>
            <pattern id="rain-right" width="34" height="58" patternUnits="userSpaceOnUse" patternTransform="rotate(16)">
              <line x1="6" y1="4" x2="6" y2="40" stroke="#73808b" strokeWidth="1.6" strokeLinecap="round" />
            </pattern>
          </defs>
          <path d="M520 430V20c-40 10-80 50-120 100-70 90-150 200-260 280-30 18-70 28-140 30z" fill="#56636f" />
          <path d="M520 430V20c-40 10-80 50-120 100-70 90-150 200-260 280-30 18-70 28-140 30z" fill="url(#rain-right)" />
          <path d="M520 430V250c-50 30-100 90-140 180z" fill="#44505c" />
        </svg>
        <div className="intro-water">
          <svg viewBox="0 0 1600 340" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            <path d="M0 0h700C560 40 300 90 0 140z" fill="#5c6876" opacity="0.2" />
            <path d="M1600 0h-420c120 40 270 80 420 110z" fill="#56636f" opacity="0.2" />
          </svg>
          {GLINTS.map(([left, top, width, kind], i) => (
            <span
              key={i}
              className={`intro-glint${kind === 'dark' ? ' dark' : ''}`}
              style={{ left: `${left}%`, top: `${top}%`, width: `${width}%`, animationDelay: `${-i * 1.3}s` }}
            />
          ))}
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={`sun-${i}`}
              className="intro-glint sun"
              style={{
                left: `calc(68vw + 8.5vmin - ${(6 - i) * 0.9}vmin)`,
                top: `${4 + i * 5}%`,
                width: `${(6 - i) * 1.8}vmin`,
                opacity: 1 - i * 0.16,
              }}
            />
          ))}
        </div>
        <div className="intro-action" ref={actionRef}>
          <svg viewBox="0 0 820 520">
            <g ref={boatRef}>
              <path d="M102 404c68 14 198 14 302 2l-12 24c-92 10-212 10-276-4z" fill="#8b959c" opacity="0.55" />
              <path d="M52 330c68 16 248 22 368 24l-16 48c-104 10-234 10-302-4-22-18-40-46-50-68z" fill="#232e3a" />
              <path d="M74 350c86 12 226 16 340 18M90 372c90 10 210 14 318 14" stroke="#3a4655" strokeWidth="2" fill="none" />
              <path d="M52 330c68 16 248 22 368 24" stroke="#4a5767" strokeWidth="3" fill="none" strokeLinecap="round" />
              <path d="M232 343v-9M226 334h12" stroke="#4a5767" strokeWidth="3" strokeLinecap="round" />
              {/* the fisherman: a navy silhouette, standing */}
              <path d="M264 288l-18 60M278 288l20 60" stroke="#1c2836" strokeWidth="15" strokeLinecap="round" />
              <path d="M270 222q16 32 46 24" stroke="#1c2836" strokeWidth="12" fill="none" strokeLinecap="round" />
              <path d="M246 294c-6-30-2-70 16-86l18-2c16 10 22 46 16 88z" fill="#142130" />
              <circle cx="270" cy="186" r="15" fill="#142130" />
              <path d="M256 182c0-16 28-18 30-2z" fill="#142130" />
              <path d="M280 177l24 4-20 5z" fill="#142130" />
              <path d="M284 218q16 28 38 20" stroke="#142130" strokeWidth="13" fill="none" strokeLinecap="round" />
              <g ref={rodRef} transform={`rotate(${ANGLE_REST} ${HANDS.x} ${HANDS.y})`}>
                <path ref={rodPathRef} d={rest.d} stroke="#142130" strokeWidth="4" fill="none" strokeLinecap="round" />
                <circle cx={HANDS.x - 12} cy={HANDS.y + 9} r="7" fill="#142130" />
              </g>
              <circle cx={HANDS.x} cy={HANDS.y} r="6.5" fill="#142130" />
            </g>
            <path ref={lineRef} d="" stroke="#142130" strokeWidth="1.4" fill="none" />
            <g ref={rippleRef} className="intro-ripple">
              <ellipse cx={FISH_REST.x + 30} cy={FISH_REST.y + 10} rx="34" ry="6" fill="none" stroke="#fff" strokeWidth="1.6" />
              <ellipse cx={FISH_REST.x + 30} cy={FISH_REST.y + 10} rx="34" ry="6" fill="none" stroke="#fff" strokeWidth="1.6" />
            </g>
            <g ref={splashRef} className="intro-splash">
              {DROPLETS.map(([dx, dy], i) => (
                <circle
                  key={i}
                  cx={FISH_REST.x + 24}
                  cy={FISH_REST.y}
                  r={i % 2 ? 3.2 : 4.2}
                  fill="#fff"
                  style={{ ['--dx' as string]: `${dx}px`, ['--dy' as string]: `${dy}px` }}
                />
              ))}
            </g>
            {/* the salmon, mouth at the origin, body trailing to the right */}
            <g ref={fishRef} transform={`translate(${FISH_REST.x} ${FISH_REST.y}) rotate(26)`}>
              <path d="M0 0c16-17 62-24 100-9l14 6v6l-14 6C62 24 16 17 0 0z" fill="#cdd4d8" />
              <path d="M0 0c16-17 62-24 100-9l14 6H56C36-4 16-3 0 0z" fill="#8f9ba5" />
              <path d="M8 2c32 5 72 3 100-1" stroke="#e5a395" strokeWidth="3.2" fill="none" strokeLinecap="round" />
              <path d="M112 0l26-18-7 18 7 18z" fill="#8f9ba5" />
              <path d="M48-19l14-12 10 13z" fill="#8f9ba5" />
              <path d="M60 15l10 9 6-10z" fill="#aeb8bf" />
              <circle cx="40" cy="-10" r="1.6" fill="#6d7983" />
              <circle cx="55" cy="-12" r="1.6" fill="#6d7983" />
              <circle cx="70" cy="-9" r="1.6" fill="#6d7983" />
              <circle cx="13" cy="-4" r="2.4" fill="#142130" />
              <path d="M2 2l7 2" stroke="#6d7983" strokeWidth="1.5" strokeLinecap="round" />
            </g>
          </svg>
        </div>
      </div>

      <div className="intro-copy" ref={copyRef}>
        <h1 id="intro-title" className="intro-title">
          Salmon Signal
        </h1>
        <p className="intro-sub">
          An open test of whether Norway's free farm-level biology data forecasts salmon supply and price.
        </p>
      </div>

      <div className="intro-cta" ref={ctaRef}>
        <button type="button" ref={buttonRef} className="btn btn-primary reel-btn">
          <IconReel size={20} /> Reel in
        </button>
        <span className="or-scroll">or scroll</span>
      </div>

      <aside className="oslo-card" ref={cardRef} aria-label="Next official figures">
        <OsloCard hasCurrentCall={hasCurrentCall} />
      </aside>
    </section>
  );
}

// ---- The Oslo card: live clock and the countdown to the next release ----

function osloParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Oslo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return { y: Number(get('year')), m: Number(get('month')), d: Number(get('day')), time: `${get('hour')}:${get('minute')}` };
}

/** Days until the 20th, when the Directorate publishes the previous month (00-shared.md). */
export function daysToRelease(y: number, m: number, d: number): number {
  let ty = y;
  let tm = m;
  if (d > 20) {
    tm += 1;
    if (tm > 12) {
      tm = 1;
      ty += 1;
    }
  }
  return Math.round((Date.UTC(ty, tm - 1, 20) - Date.UTC(y, m - 1, d)) / 86_400_000);
}

function OsloCard({ hasCurrentCall }: { hasCurrentCall: boolean }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  const { y, m, d, time } = osloParts(now);
  const days = daysToRelease(y, m, d);
  return (
    <>
      <p className="oslo-top">
        <span className="oslo-place">
          <span className="oslo-dot" aria-hidden="true" /> Oslo
        </span>
        <span className="oslo-time">{time}</span>
      </p>
      <p>
        {days === 0 ? (
          <>Official harvest figures come out <strong>today</strong>.</>
        ) : (
          <>
            Next official harvest figures in <strong>{days === 1 ? '1 day' : `${days} days`}</strong>.
          </>
        )}{' '}
        {hasCurrentCall ? 'Our call goes in first.' : 'See how our calls on the 10th did.'}
      </p>
    </>
  );
}
