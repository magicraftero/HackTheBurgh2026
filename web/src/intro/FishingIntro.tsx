import { useEffect, useRef, type RefObject } from 'react';
import { FishMark } from '../components/Icons';

/*
  The intro: a fisherman in a boat. The site hangs on his line under the water.
  On load he gets a bite, lifts the rod, and the site rises out of the sea.

  How it works: the scene is a sticky, full-screen layer behind the site, and
  the site starts 10vh above the bottom of the screen. Everything is driven by
  scroll position: the auto-play simply scrolls the page, so scrolling by hand
  plays (and rewinds) the same animation. One rAF loop moves the rod, the line,
  the water and the splash; it stops once the site covers the screen.

  Accessibility: the scene is decorative (aria-hidden). "Skip intro" is the
  first thing in the tab order; any key, wheel or touch stops the auto-play;
  reduced-motion users start with the site already in place.
*/

const DRAWING_W = 400; // the boat drawing's width, in its own units
const WATERLINE = 250; // where the hull meets the water, in drawing units
const PIVOT = { x: 238, y: 182 }; // the fisherman's hands
const ROD_LENGTH = 250;
const ANGLE_START = -12; // degrees; negative tilts the tip up
const ANGLE_END = -62;
const SURFACE = 0.62; // the sea surface, as a share of the screen height
const AUTOPLAY_DELAY = 1500; // ms: idle, then the bite
const AUTOPLAY_TIME = 1900; // ms: the pull

export const REPLAY_EVENT = 'salmon-signal:replay-intro';

const clamp = (x: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, x));
const easeOut = (u: number) => 1 - Math.pow(1 - u, 3);
const easeInOut = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
const bump = (t: number, centre: number, width: number) => Math.exp(-(((t - centre) / width) ** 2));

/** The rod in drawing units: its path (before rotation) and its tip (after). */
function rodShape(deg: number, bend: number) {
  const butt = { x: PIVOT.x - 16, y: PIVOT.y + 5 };
  const tip = { x: PIVOT.x + ROD_LENGTH, y: PIVOT.y + bend };
  const ctrl = { x: PIVOT.x + ROD_LENGTH * 0.55, y: PIVOT.y + bend * 0.2 };
  const a = (deg * Math.PI) / 180;
  const dx = tip.x - PIVOT.x;
  const dy = tip.y - PIVOT.y;
  return {
    d: `M${butt.x} ${butt.y} Q${ctrl.x} ${ctrl.y} ${tip.x} ${tip.y}`,
    tip: {
      x: PIVOT.x + dx * Math.cos(a) - dy * Math.sin(a),
      y: PIVOT.y + dx * Math.sin(a) + dy * Math.cos(a),
    },
  };
}

const DROPLETS = [
  { dx: '-46px', dy: '-58px', s: '9px' },
  { dx: '-22px', dy: '-84px', s: '7px' },
  { dx: '4px', dy: '-96px', s: '10px' },
  { dx: '28px', dy: '-80px', s: '7px' },
  { dx: '50px', dy: '-52px', s: '9px' },
  { dx: '-64px', dy: '-26px', s: '6px' },
  { dx: '66px', dy: '-24px', s: '6px' },
];

export function FishingIntro({ siteRef }: { siteRef: RefObject<HTMLDivElement | null> }) {
  const sceneRef = useRef<HTMLDivElement>(null);
  const boatRef = useRef<HTMLDivElement>(null);
  const rodRef = useRef<SVGGElement>(null);
  const rodPathRef = useRef<SVGPathElement>(null);
  const lineSvgRef = useRef<SVGSVGElement>(null);
  const lineRef = useRef<SVGPathElement>(null);
  const rippleRef = useRef<HTMLDivElement>(null);
  const brandRef = useRef<HTMLDivElement>(null);
  const waterRef = useRef<HTMLDivElement>(null);
  const splashRef = useRef<HTMLDivElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    const boat = boatRef.current;
    const rod = rodRef.current;
    const rodPath = rodPathRef.current;
    const lineSvg = lineSvgRef.current;
    const line = lineRef.current;
    const ripple = rippleRef.current;
    const brand = brandRef.current;
    const water = waterRef.current;
    const splash = splashRef.current;
    const skip = skipRef.current;
    const site = siteRef.current;
    if (!scene || !boat || !rod || !rodPath || !lineSvg || !line || !ripple || !brand || !water || !splash || !skip || !site) {
      return;
    }

    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

    // ---- Geometry, in screen pixels ----
    let vw = 0;
    let vh = 0;
    let surfaceY = 0;
    let scale = 1; // screen px per drawing unit
    let boatW = 0;
    let boatX = 0;
    let boatY = 0;
    let hookX = 0;
    let travel = 1; // scroll distance until the site reaches the top

    const measure = () => {
      vw = window.innerWidth;
      vh = window.innerHeight;
      surfaceY = Math.round(vh * SURFACE);
      boatW = clamp(Math.min(vw, vh) * 0.36, 230, 440);
      scale = boatW / DRAWING_W;
      hookX = Math.round(vw * (vw < 720 ? 0.74 : 0.57));
      boatX = hookX - rodShape(ANGLE_START, 6).tip.x * scale;
      boatY = surfaceY - WATERLINE * scale;
      boat.style.width = `${boatW}px`;
      boat.style.left = `${boatX}px`;
      boat.style.top = `${boatY}px`;
      scene.style.setProperty('--surface', `${surfaceY}px`);
      water.style.setProperty('--surface', `${surfaceY}px`);
      site.style.setProperty('--hook-x', `${hookX}px`);
      lineSvg.setAttribute('viewBox', `0 0 ${vw} ${vh}`);
      travel = Math.max(1, site.getBoundingClientRect().top + window.scrollY);
    };

    // ---- Auto-play ----
    const t0 = performance.now();
    let autoAt = 0; // when the pull should start
    let auto: { from: number; to: number; start: number } | null = null;
    let biteFrom = t0;

    const startAutoplay = () => {
      window.scrollTo(0, 0);
      biteFrom = performance.now();
      autoAt = biteFrom + AUTOPLAY_DELAY;
      auto = null;
      wake();
    };
    const stopAutoplay = () => {
      autoAt = 0;
      auto = null;
    };
    const skipIntro = () => {
      stopAutoplay();
      window.scrollTo(0, travel);
      document.getElementById('top-heading')?.focus({ preventScroll: true });
    };

    // ---- One frame ----
    let raf = 0;
    let prevHookY = Number.POSITIVE_INFINITY;
    let hidden = false;

    const render = (now: number) => {
      const p = clamp(window.scrollY / travel, 0, 1);
      const time = (now - t0) / 1000;
      const sinceBite = (now - biteFrom) / 1000;

      // The bite: two tugs on the line before the pull.
      const tugs = autoAt || auto ? bump(sinceBite, 0.75, 0.09) + 1.2 * bump(sinceBite, 1.08, 0.09) : 0;

      // The boat bobs.
      const bob = reduce ? 0 : Math.sin(time * 2.1) * 3;
      const tilt = reduce ? 0 : Math.sin(time * 2.1 + 0.8) * 1.1;
      boat.style.transform = `translate3d(0, ${bob.toFixed(2)}px, 0) rotate(${tilt.toFixed(3)}deg)`;

      // The rod lifts as the site rises, and bends under the load.
      const lift = easeOut(clamp(p / 0.55, 0, 1));
      const deg = ANGLE_START + (ANGLE_END - ANGLE_START) * lift;
      const bend = 6 + 26 * Math.sin(Math.PI * clamp(p / 0.6, 0, 1)) + 20 * tugs;
      const shape = rodShape(deg, bend);
      rod.setAttribute('transform', `rotate(${deg.toFixed(2)} ${PIVOT.x} ${PIVOT.y})`);
      rodPath.setAttribute('d', shape.d);

      // Rod tip on screen, following the boat's bob and tilt.
      const ox = boatW * 0.5;
      const oy = WATERLINE * scale;
      const lx = shape.tip.x * scale - ox;
      const ly = shape.tip.y * scale - oy;
      const a = (tilt * Math.PI) / 180;
      const tipX = boatX + ox + lx * Math.cos(a) - ly * Math.sin(a);
      const tipY = boatY + oy + lx * Math.sin(a) + ly * Math.cos(a) + bob;

      // The hook: on the site's top edge, which dips during the bite.
      const dip = 12 * tugs;
      site.style.transform = dip > 0.2 ? `translate3d(0, ${dip.toFixed(2)}px, 0)` : '';
      const siteTop = site.getBoundingClientRect().top;
      const hookY = siteTop - 42;
      const wobble = 10 * tugs * Math.sin(time * 40);
      const midX = (tipX + hookX) / 2 + wobble;
      const midY = (tipY + hookY) / 2;
      line.setAttribute('d', `M${tipX.toFixed(1)} ${tipY.toFixed(1)} Q${midX.toFixed(1)} ${midY.toFixed(1)} ${hookX} ${hookY.toFixed(1)}`);

      // Once the site rises past the rod tip, the catch is landed: the line and hook fade.
      const landed = clamp((siteTop - tipY + 50) / 60, 0, 1);
      line.style.opacity = landed.toFixed(3);
      site.style.setProperty('--hook-o', landed.toFixed(3));

      // Ripples where the line enters the water, while the hook is under it.
      if (hookY > surfaceY + 4 && hookY !== tipY) {
        const x = tipX + ((hookX - tipX) * (surfaceY - tipY)) / (hookY - tipY);
        ripple.style.transform = `translate(${x.toFixed(1)}px, ${surfaceY}px)`;
        ripple.style.opacity = '1';
      } else {
        ripple.style.opacity = '0';
      }

      // A splash as the site breaks the surface.
      if (prevHookY > surfaceY && hookY <= surfaceY && !reduce) {
        splash.style.transform = `translate(${hookX}px, ${surfaceY}px)`;
        splash.classList.remove('go');
        void splash.offsetWidth; // restart the animation
        splash.classList.add('go');
      }
      prevHookY = hookY;

      // The water in front fades once the site is out of it.
      const fade = 0.07 * vh;
      water.style.opacity = clamp((siteTop - (surfaceY - fade)) / fade, 0, 1).toFixed(3);

      brand.style.opacity = clamp(1 - p * 3, 0, 1).toFixed(3);
      skip.classList.toggle('is-gone', p > 0.9);
      site.style.setProperty('--panel-r', `${(32 * (1 - clamp((p - 0.88) / 0.12, 0, 1))).toFixed(1)}px`);

      // Once the site covers the screen, hide the scene so it costs nothing.
      const covered = p >= 1 && !auto && !autoAt;
      if (covered !== hidden) {
        hidden = covered;
        const v = covered ? 'hidden' : 'visible';
        scene.style.visibility = v;
        water.style.visibility = v;
      }
      return covered;
    };

    const loop = (now: number) => {
      raf = 0;
      if (autoAt && now >= autoAt) {
        auto = { from: window.scrollY, to: travel, start: now };
        autoAt = 0;
      }
      if (auto) {
        const u = clamp((now - auto.start) / AUTOPLAY_TIME, 0, 1);
        window.scrollTo(0, auto.from + (auto.to - auto.from) * easeInOut(u));
        if (u >= 1) auto = null;
      }
      const covered = render(now);
      if (!covered) raf = requestAnimationFrame(loop);
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
      if (e instanceof KeyboardEvent && e.key === 'Tab') return;
      stopAutoplay();
    };
    const inputs = ['wheel', 'touchstart', 'pointerdown', 'keydown'] as const;

    measure();
    window.addEventListener('scroll', wake, { passive: true });
    window.addEventListener('resize', onResize);
    window.addEventListener(REPLAY_EVENT, startAutoplay);
    for (const name of inputs) window.addEventListener(name, onUserInput, { passive: true });
    skip.addEventListener('click', skipIntro);

    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (target) {
      requestAnimationFrame(() => target.scrollIntoView());
    } else if (reduce) {
      window.scrollTo(0, travel);
    } else {
      startAutoplay();
    }
    wake();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', wake);
      window.removeEventListener('resize', onResize);
      window.removeEventListener(REPLAY_EVENT, startAutoplay);
      for (const name of inputs) window.removeEventListener(name, onUserInput);
      skip.removeEventListener('click', skipIntro);
      site.style.transform = '';
    };
  }, [siteRef]);

  return (
    <>
      <div className="intro" ref={sceneRef} aria-hidden="true">
        <div className="intro-sun" />
        <div className="intro-cloud c1" />
        <div className="intro-cloud c2" />
        <div className="intro-cloud c3" />
        <svg className="intro-mountains" viewBox="0 0 1440 200" preserveAspectRatio="none">
          <path
            d="M0 200V118l120-50 110 45 110-75 130 70 90-30 130 50 130-70 120 60 120-45 120 50 120-70 140 55v90z"
            fill="#f2c3b6"
          />
          <path
            d="M0 200v-42l150-38 110 30 140-50 120 60 120-25 120 35 140-50 130 45 130-25 140 30 140-40v70z"
            fill="#e7a596"
          />
        </svg>
        <div className="intro-sea" />
        <svg className="intro-pens" viewBox="0 0 200 20" preserveAspectRatio="xMidYMid meet" style={{ position: 'absolute', left: '64vw', width: '220px', top: 'calc(var(--surface, 62vh) - 9px)' }}>
          <ellipse cx="40" cy="10" rx="34" ry="6" fill="none" stroke="#ffe3da" strokeWidth="3" />
          <ellipse cx="130" cy="10" rx="28" ry="5" fill="none" stroke="#ffe3da" strokeWidth="3" />
        </svg>
        <div className="intro-boat" ref={boatRef}>
          <svg viewBox="0 0 400 300">
            {/* inside of the boat */}
            <path d="M40 226q150 14 300 0l-4 10q-146 12-292 0z" fill="#8f3b27" />
            {/* the fisherman: yellow raincoat and sou'wester */}
            <path d="M148 232l2-60q2-22 26-24h18q22 3 23 26l3 58z" fill="#f6c445" />
            <path d="M183 152v78" stroke="#e0a92e" strokeWidth="3" />
            <path d="M160 170q10 26 54 22" stroke="#e8b43a" strokeWidth="13" fill="none" strokeLinecap="round" />
            <circle cx="183" cy="128" r="17" fill="#f1c6a8" />
            <path d="M169 131q2 21 17 21 13-1 14-20-7 9-15 9-9 0-16-10z" fill="#ded6cc" />
            <circle cx="200" cy="129" r="3.4" fill="#e9ae8f" />
            <circle cx="192" cy="124" r="1.9" fill="#0b0b0c" />
            <path d="M165 120q1-21 19-22 17 1 18 22z" fill="#f6c445" />
            <path d="M150 121q34-10 66-1-32 9-66 1z" fill="#e8b43a" />
            <path d="M160 121q-2 17 6 25" stroke="#f6c445" strokeWidth="7" fill="none" strokeLinecap="round" />
            <path d="M200 166q14 16 32 18" stroke="#f6c445" strokeWidth="14" fill="none" strokeLinecap="round" />
            {/* the rod, which rotates around his hands */}
            <g ref={rodRef} transform={`rotate(${ANGLE_START} ${PIVOT.x} ${PIVOT.y})`}>
              <path ref={rodPathRef} d={rodShape(ANGLE_START, 6).d} stroke="#3a2a22" strokeWidth="3.6" fill="none" strokeLinecap="round" />
              <circle cx="228" cy="191" r="6.5" fill="#2b2b2e" />
              <circle cx="228" cy="191" r="2.2" fill="#a3a3a3" />
            </g>
            <circle cx="236" cy="183" r="7.5" fill="#f1c6a8" />
            {/* the hull */}
            <path d="M26 224h328l-32 42q-132 20-256 0z" fill="#f27a5e" />
            <path d="M31 231h318l-5 7H37z" fill="#fff" opacity="0.92" />
            <path d="M26 224h328" stroke="#b8462c" strokeWidth="4" strokeLinecap="round" />
          </svg>
        </div>
        <svg className="intro-line" ref={lineSvgRef} preserveAspectRatio="none">
          <path ref={lineRef} d="" stroke="#2b2b2e" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        </svg>
        <div className="intro-ripple" ref={rippleRef} />
        <div className="intro-brand" ref={brandRef}>
          <span className="wordmark">
            <FishMark /> Salmon Signal
          </span>
          <p>Reeling in the findings…</p>
        </div>
      </div>
      <div className="intro-water" ref={waterRef} aria-hidden="true" />
      <div className="intro-splash" ref={splashRef} aria-hidden="true">
        {DROPLETS.map((d, i) => (
          <span key={i} style={{ ['--dx' as string]: d.dx, ['--dy' as string]: d.dy, ['--s' as string]: d.s }} />
        ))}
      </div>
      <button type="button" ref={skipRef} className="btn btn-light btn-sm intro-skip">
        Skip intro
      </button>
    </>
  );
}

/** The hook and ring on the site's top edge, where the line ties on. */
export function Hook() {
  return (
    <svg className="hook" viewBox="0 0 28 52" aria-hidden="true" focusable="false">
      <circle cx="14" cy="7" r="5" fill="none" stroke="#2b2b2e" strokeWidth="2.6" />
      <path d="M14 12v22q0 9 8 9" fill="none" stroke="#2b2b2e" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M9 52a5 5 0 0 1 10 0" fill="#2b2b2e" />
    </svg>
  );
}
