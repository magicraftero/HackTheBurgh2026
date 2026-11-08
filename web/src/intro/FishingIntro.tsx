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

  The cast is drawn like the rest of the scene: flat shapes, no outlines, small
  plain eyes, and only the scene's colours (navy, slate, mist, cream, one coral).
  They are all waiting for the same fish: the fisherman nods off and
  jerks awake at every tug; his cat stares at the line and stands up when the
  salmon rises; the salmon is unimpressed until it leaves the water, and watches
  the pointer; a gull sits on the title's l (point at it and it squawks; click
  it and it flies to the other l) and flees when the reel-in starts; the left mountain is a sleeping giant
  who wakes for the catch, or if you hover over him; and every tug sends a
  signal from the rod tip, which is where the name comes from.

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
/** 0 outside a to b; inside, it rises to 1 and falls back. */
const bump = (x: number, a: number, b: number) => {
  const edge = Math.min(0.35, (b - a) / 3);
  return clamp(Math.min((x - a) / edge, (b - x) / edge), 0, 1);
};

// The left mountain's ridge: a giant lying on his back, face to the sky.
const GIANT =
  'M0 470V60c30-30 90-52 130-46C165 20 195 58 216 83C221 92 222 104 223 111C240 104 266 96 285 105C300 112 298 136 281 152' +
  'C288 152 298 152 302 159C304 165 304 171 304 175C310 172 318 173 320 179C322 188 326 198 329 203C342 200 360 198 365 208' +
  'C372 226 370 248 368 262C384 282 410 292 436 300C470 318 495 340 520 360c70 50 150 90 240 110z';
const GIANT_EYE = { x: 220, y: 137, angle: 44 }; // in the mountain's own drawing

const GULL_BODY = 'M20 36C27 29 40 28 50 32C62 37 76 47 88 57L84 61C72 66 56 69 44 67C30 65 20 56 19 46C19 42 19 39 20 36z';
const GULL_WING = 'M38 42C38 26 46 8 60-6L68-2C64 12 62 28 60 44z';
const GULL_WING_TIP = 'M60-6L76-20 68-2z';

/** The fisherman's scarf, streaming out behind him in drawing units. */
function scarf(time: number, wind: number) {
  let d = 'M258 208';
  for (let i = 1; i <= 7; i++) {
    const wave = Math.sin(time * 3.4 - i * 0.85) * (0.8 + i * 0.75) * (1 + wind);
    d += `L${258 - i * 10} ${(208 + i * 2.6 + wave).toFixed(1)}`;
  }
  return d;
}

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

    // The cast is decoration: if a part is missing, the reel-in still works.
    const part = <T extends SVGElement | HTMLElement = SVGElement>(name: string) => scene.querySelector<T>(`[data-part="${name}"]`);
    const fisherman = part('fisherman');
    const head = part('head');
    const bobble = part('bobble');
    const scarfLine = part('scarf');
    const scarfStripes = part('scarf-stripes');
    const cat = part('cat');
    const catHead = part('cat-head');
    const catTail = part('cat-tail');
    const fishEye = part('fish-eye');
    const fishPupil = part('fish-pupil');
    const fishLid = part('fish-lid');
    const signal = part('signal');
    const signalArcs = Array.from(signal?.querySelectorAll('path') ?? []);
    const giant = part('giant');
    const giantShut = part('giant-shut');
    const giantOpen = part('giant-open');
    const giantPupil = part('giant-pupil');
    const giantSnore = part('giant-snore');
    const gull = part<HTMLElement>('gull');
    const gullHead = part('gull-head');
    const gullBeak = part('gull-beak');
    const gullFolded = part('gull-folded');
    const gullLegs = part('gull-legs');
    const gullNear = part('gull-near');
    const gullFar = part('gull-far');
    const gullArt = gull?.querySelector('svg') ?? null;
    const titleEl = copy.querySelector('h1');

    let travel = 1; // scroll distance until the site reaches the top
    let actionTop = 0;
    let actionLeft = 0;
    let scale = 1;
    let vw = window.innerWidth;
    let vh = window.innerHeight;
    let copyShift = 0; // how far the headline has been moved up right now

    let pointer: { x: number; y: number } | null = null; // mouse only
    let eager = 0; // 1 while the pointer is on "Reel in": the salmon knows
    let eagerTarget = 0;
    let lookUntil = 0; // he looks over his shoulder if you click him
    let turned = 0;
    let giantHover = false;
    let giantAwake = 0;
    let giantEye = { x: 0, y: 0 };
    let perches: { x: number; y: number }[] = []; // the tops of the title's two l's
    let gullSize = 60;
    let gullOn = 1; // starts on the last l
    let gullHop: { from: number; to: number; start: number } | null = null;
    let gullHover = false;
    let gullFacing = 1; // 1 is left; it passes through 0 as the bird turns round
    let gullSquawk = 0;
    let navBottom = 0; // the gull stays below the top bar
    let titleBox = '';

    // Where the tops of the l's are: the letters' ink, from the font's own numbers.
    const measurePerches = () => {
      const title = copy.querySelector('h1');
      const text = title?.firstChild;
      const ctx = document.createElement('canvas').getContext('2d');
      if (!title || !text || text.nodeType !== Node.TEXT_NODE || !ctx) return;
      const style = getComputedStyle(title);
      const size = parseFloat(style.fontSize);
      const spacing = parseFloat(style.letterSpacing) || 0;
      ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const m = ctx.measureText('l');
      const gap = m.fontBoundingBoxAscent - m.actualBoundingBoxAscent;
      const found: { x: number; y: number }[] = [];
      const letters = text.textContent ?? '';
      for (let i = 0; i < letters.length; i++) {
        if (letters[i] !== 'l') continue;
        const range = document.createRange();
        range.setStart(text, i);
        range.setEnd(text, i + 1);
        const r = range.getBoundingClientRect();
        // Letter-spacing is added to the right of each letter, so leave it out.
        found.push({ x: r.left + (r.width - spacing) / 2, y: r.top + gap - copyShift });
      }
      perches = found;
      gullSize = size * 0.56;
      if (gull) gull.style.width = `${gullSize}px`;
      navBottom = (document.querySelector('.float-nav nav') ?? document.querySelector('.float-nav'))?.getBoundingClientRect().bottom ?? 0;
    };

    const measure = () => {
      vw = window.innerWidth;
      vh = window.innerHeight;
      const width = vw >= 720 ? clamp(vw * 0.6, 600, 1000) : 560;
      const s = width / VIEW_W;
      const left = vw >= 720 ? (vw - width) / 2 : vw - 50 - FISH_REST.x * s;
      action.style.width = `${width}px`;
      action.style.left = `${left}px`;
      actionLeft = left;
      actionTop = vh * 0.8 - WATERLINE * s;
      scale = s;
      action.style.top = `${actionTop}px`;
      travel = Math.max(1, site.getBoundingClientRect().top + window.scrollY);
      measurePerches();
      if (giantShut) {
        const r = giantShut.getBoundingClientRect();
        giantEye = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
      }
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

      // If the title moves or changes size for any reason, the gull's perches move too.
      if (titleEl) {
        const b = titleEl.getBoundingClientRect();
        const box = [b.left, b.top - copyShift, b.width, b.height].map(Math.round).join();
        if (box !== titleBox) {
          titleBox = box;
          measurePerches();
        }
      }

      // Idle life: the boat rocks, and every few seconds the salmon fights
      // (harder if the pointer is on the button).
      eager = reduce ? 0 : eager + (eagerTarget - eager) * 0.12;
      const bob = Math.sin(time * 1.6) * 2.2;
      const natural = reduce ? 0 : Math.pow(Math.max(0, Math.sin(time * 1.4)), 16);
      const tug = Math.max(natural, eager * (0.55 + 0.45 * Math.sin(time * 9)));
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
      const fishAngle = lerp(26, 84, lift) + fight;
      fish.setAttribute('transform', `translate(${fx.toFixed(1)} ${fy.toFixed(1)}) rotate(${fishAngle.toFixed(2)})`);

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

      // ---- The cast ----
      // He dozes between tugs, and every tug wakes him with a jerk.
      const cycle = (((time * 1.4 - Math.PI / 2) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      const droop = reduce ? 0 : 11 * easeInOut(clamp((cycle / (2 * Math.PI) - 0.2) / 0.7, 0, 1)) * (1 - heave) * (1 - eager);
      turned += (Math.max(now < lookUntil ? 1 : 0, reduce ? 0 : bump(time % 17, 12.5, 14.2)) - turned) * (reduce ? 1 : 0.14);
      head?.setAttribute('transform', `rotate(${droop.toFixed(2)} 270 205) translate(270 0) scale(${(1 - 2 * turned).toFixed(3)} 1) translate(-270 0)`);
      bobble?.setAttribute('cy', (158 + Math.sin(time * 3.2) * 1.3 - 4 * tug).toFixed(2));
      const scarfShape = scarf(time, heave * 1.2);
      scarfLine?.setAttribute('d', scarfShape);
      scarfStripes?.setAttribute('d', scarfShape);

      // The cat stares at the line, and stands to follow the salmon up.
      cat?.setAttribute('transform', `translate(380 356) scale(1 ${(1 + 0.2 * lift).toFixed(3)})`);
      catHead?.setAttribute('transform', `rotate(${(lerp(14, -46, lift) + Math.sin(time * 0.6) * 3 - 6 * tug).toFixed(2)} 5 -32)`);
      catTail?.setAttribute('d', `M-12 1C-26 3 ${(-36 + 3 * Math.sin(time * 1.7)).toFixed(1)} -8 ${(-31 + (5 + 9 * tug) * Math.sin(time * 2.3)).toFixed(1)} -25`);

      // The salmon looks unimpressed until it leaves the water, and watches the pointer.
      const openEyed = Math.max(lift, eager * 0.8);
      fishLid?.setAttribute('transform', `translate(0 ${(-7 * openEyed).toFixed(2)})`);
      fishEye?.setAttribute('transform', `translate(14 -5) scale(${(1 + 0.15 * openEyed).toFixed(3)}) translate(-14 5)`);
      if (fishPupil && !reduce) {
        const a = (fishAngle * Math.PI) / 180;
        const ex = fx + 14 * Math.cos(a) + 5 * Math.sin(a);
        const ey = fy + 14 * Math.sin(a) - 5 * Math.cos(a);
        const dx = (pointer ? (pointer.x - actionLeft) / scale : 322) - ex; // no mouse: he glares at the fisherman
        const dy = (pointer ? (pointer.y - actionTop) / scale : 238) - ey;
        const len = Math.hypot(dx, dy) || 1;
        fishPupil.setAttribute('cx', (14 + ((dx * Math.cos(a) + dy * Math.sin(a)) / len) * 1.4).toFixed(2));
        fishPupil.setAttribute('cy', (-5 + ((-dx * Math.sin(a) + dy * Math.cos(a)) / len) * 1.4).toFixed(2));
      }

      // Every tug sends a signal from the rod tip.
      if (signal) {
        signal.setAttribute('transform', `translate(${tipX.toFixed(1)} ${tipY.toFixed(1)})`);
        signalArcs.forEach((arc, i) => {
          arc.style.opacity = (clamp(tug * 1.6 - i * 0.25, 0, 1) * (1 - lift)).toFixed(3);
        });
      }

      // The giant sleeps; he wakes for the catch, for a pointer, and now and then to check.
      const wantAwake = Math.max(clamp((p - 0.02) / 0.05, 0, 1), giantHover ? 1 : 0, reduce ? 0 : bump(time % 23, 19.5, 21.5));
      giantAwake += (wantAwake - giantAwake) * (reduce ? 1 : 0.1);
      giantOpen?.setAttribute('transform', `scale(1 ${giantAwake.toFixed(3)})`);
      if (giantShut) giantShut.style.opacity = (1 - giantAwake).toFixed(3);
      if (giantSnore) giantSnore.style.opacity = giantAwake > 0.12 ? '0' : '1';
      if (giantPupil && !reduce) {
        const a = (GIANT_EYE.angle * Math.PI) / 180;
        const dx = (pointer && giantHover ? pointer.x : actionLeft + fx * scale) - giantEye.x;
        const dy = (pointer && giantHover ? pointer.y : actionTop + fy * scale) - giantEye.y;
        const len = Math.hypot(dx, dy) || 1;
        giantPupil.setAttribute('cx', (((dx * Math.cos(a) + dy * Math.sin(a)) / len) * 9).toFixed(2));
        giantPupil.setAttribute('cy', (((-dx * Math.sin(a) + dy * Math.cos(a)) / len) * 3).toFixed(2));
      }

      // The gull keeps an eye on things, and leaves the moment anything happens.
      if (gull && perches.length) {
        const rest = perches[Math.min(gullOn, perches.length - 1)]!;
        let gx = rest.x;
        let gy = rest.y;
        let flying = false;
        let want = !reduce && bump(time % 19, 11, 15) > 0.5 ? -1 : 1; // now and then it turns round on its post
        if (gullHop) {
          const u = clamp((now - gullHop.start) / 1400, 0, 1);
          const a = perches[gullHop.from] ?? rest;
          const b = perches[gullHop.to] ?? rest;
          // Up and over if there's room under the top bar (wings raised), otherwise a swoop down.
          const headroom = Math.min(a.y, b.y) - gullSize * 1.1 - navBottom - 8;
          const arc = headroom > gullSize * 0.3 ? Math.min(gullSize * 0.9, headroom) : -gullSize * 0.4;
          gx = lerp(a.x, b.x, easeInOut(u));
          gy = lerp(a.y, b.y, easeInOut(u)) - Math.sin(Math.PI * u) * arc;
          flying = u < 1;
          want = b.x > a.x ? -1 : 1;
          if (u >= 1) gullHop = null;
        }
        const away = clamp(p / 0.14, 0, 1);
        if (away > 0) {
          // Off the nearest side of the screen, not across the top bar.
          const side = gullOn === 0 ? -1 : 1;
          gx += away * away * vw * 0.5 * side;
          gy -= away * away * vh * 0.75;
          flying = true;
          want = side > 0 ? -1 : 1;
        }
        gullFacing = reduce ? want : gullFacing + (want - gullFacing) * 0.3;
        const flip = Math.abs(gullFacing) < 0.12 ? (gullFacing < 0 ? -0.12 : 0.12) : gullFacing;
        gull.style.transform = `translate3d(${gx.toFixed(1)}px, ${gy.toFixed(1)}px, 0) translate(-50%, -97%) scaleX(${flip.toFixed(3)})`;
        gull.style.visibility = away >= 1 ? 'hidden' : 'visible';

        // Wings folded on the post; spread and beating in the air.
        const folded = flying ? 'none' : '';
        const spread = flying ? '' : 'none';
        if (gullFolded) gullFolded.style.display = folded;
        if (gullLegs) gullLegs.style.display = folded;
        if (gullNear) gullNear.style.display = spread;
        if (gullFar) gullFar.style.display = spread;
        if (flying) {
          gullNear?.setAttribute('transform', `translate(0 42) scale(1 ${(0.4 + 0.6 * Math.sin(time * 18)).toFixed(3)}) translate(0 -42)`);
          gullFar?.setAttribute('transform', `translate(-8 42) scale(1 ${(0.4 + 0.6 * Math.sin(time * 18 - 0.6)).toFixed(3)}) translate(0 -42)`);
        }
        if (gullArt) gullArt.style.transform = flying ? 'rotate(-20deg)' : ''; // level in the air, upright on the post

        // It squawks if you point at it, and now and then for no reason.
        const wantSquawk = !flying && (gullHover || (!reduce && bump(time % 14.7, 11, 12) > 0)) ? 1 : 0;
        gullSquawk = reduce ? wantSquawk : gullSquawk + (wantSquawk - gullSquawk) * 0.25;
        const nod = flying || reduce ? 0 : Math.sin(time * 0.9) * 2.5;
        gullHead?.setAttribute('transform', `rotate(${(nod + 18 * gullSquawk).toFixed(2)} 30 36)`);
        gullBeak?.setAttribute('transform', `rotate(${(-26 * gullSquawk).toFixed(2)} 16 31.5)`);
      }

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
      copyShift = -40 * fadeCopy;
      copy.style.transform = `translate(-50%, ${copyShift.toFixed(1)}px)`;
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

    const onPointerMove = (e: PointerEvent) => {
      if (e.pointerType === 'mouse') pointer = { x: e.clientX, y: e.clientY };
    };
    const onButtonOver = () => {
      eagerTarget = 1;
    };
    const onButtonOut = () => {
      eagerTarget = 0;
    };
    const onFisherman = () => {
      lookUntil = performance.now() + 1500;
    };
    const onGiantOver = () => {
      giantHover = true;
    };
    const onGiantOut = () => {
      giantHover = false;
    };
    const onGullOver = () => {
      gullHover = true;
    };
    const onGullOut = () => {
      gullHover = false;
    };
    const onGull = () => {
      if (gullHop || perches.length < 2) return;
      const from = Math.min(gullOn, perches.length - 1);
      const to = (from + 1) % perches.length;
      gullOn = to;
      if (!reduce) gullHop = { from, to, start: performance.now() };
    };

    measure();
    let alive = true;
    void document.fonts?.ready.then(() => {
      if (!alive) return;
      measure();
      wake();
    });
    window.addEventListener('scroll', wake, { passive: true });
    window.addEventListener('resize', onResize);
    window.addEventListener(REPLAY_EVENT, backToBoat);
    for (const name of inputs) window.addEventListener(name, onUserInput, { passive: true });
    button.addEventListener('click', startReel);
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    button.addEventListener('pointerenter', onButtonOver);
    button.addEventListener('pointerleave', onButtonOut);
    button.addEventListener('focus', onButtonOver);
    button.addEventListener('blur', onButtonOut);
    fisherman?.addEventListener('click', onFisherman);
    giant?.addEventListener('pointerenter', onGiantOver);
    giant?.addEventListener('pointerleave', onGiantOut);
    gull?.addEventListener('pointerenter', onGullOver);
    gull?.addEventListener('pointerleave', onGullOut);
    gull?.addEventListener('click', onGull);

    const target = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    if (target) requestAnimationFrame(() => target.scrollIntoView());
    else window.scrollTo(0, 0);
    wake();

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      window.removeEventListener('scroll', wake);
      window.removeEventListener('resize', onResize);
      window.removeEventListener(REPLAY_EVENT, backToBoat);
      for (const name of inputs) window.removeEventListener(name, onUserInput);
      button.removeEventListener('click', startReel);
      window.removeEventListener('pointermove', onPointerMove);
      button.removeEventListener('pointerenter', onButtonOver);
      button.removeEventListener('pointerleave', onButtonOut);
      button.removeEventListener('focus', onButtonOver);
      button.removeEventListener('blur', onButtonOut);
      fisherman?.removeEventListener('click', onFisherman);
      giant?.removeEventListener('pointerenter', onGiantOver);
      giant?.removeEventListener('pointerleave', onGiantOut);
      gull?.removeEventListener('pointerenter', onGullOver);
      gull?.removeEventListener('pointerleave', onGullOut);
      gull?.removeEventListener('click', onGull);
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
          <path data-part="giant" d={GIANT} fill="#5c6876" />
          <path d={GIANT} fill="url(#rain-left)" pointerEvents="none" />
          <g transform={`translate(${GIANT_EYE.x} ${GIANT_EYE.y}) rotate(${GIANT_EYE.angle})`} pointerEvents="none">
            <path data-part="giant-shut" d="M-17 0q17 10 34 0" stroke="#2d3946" strokeWidth="3.4" fill="none" strokeLinecap="round" />
            <g data-part="giant-open" transform="scale(1 0)">
              <path d="M-17 0q17-13 34 0q-17 13-34 0z" fill="#f4f0ea" />
              <circle data-part="giant-pupil" r="5.6" fill="#142130" />
            </g>
          </g>
          <g data-part="giant-snore" className="intro-snore" pointerEvents="none">
            <text x="304" y="92">z</text>
            <text x="304" y="92">z</text>
            <text x="304" y="92">z</text>
          </g>
          <path d="M0 470V250c70-14 150 0 230 50 70 44 140 110 210 170z" fill="#2d3946" pointerEvents="none" />
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
        {/* Rorbuer: the red fishing cabins of the Norwegian coast, on their stilts. */}
        <svg className="intro-cabins" viewBox="0 0 260 130">
          <path d="M26 76v18M52 76v18M78 76v18M116 80v14M140 80v14M164 80v14M192 74v20M214 74v20M238 74v20" stroke="#142130" strokeWidth="3" />
          <path d="M20 44h64v34H20z" fill="#c56f50" />
          <path d="M108 50h60v32h-60z" fill="#b4603f" />
          <path d="M186 40h58v36h-58z" fill="#c56f50" />
          <path d="M13 46L52 16l39 30zM101 52l37-26 37 26zM179 42l36-28 36 28z" fill="#232e3a" />
          <path d="M150 24h9v18h-9z" fill="#232e3a" />
          <path d="M45 54h14v14H45zM131 58h13v12h-13zM208 50h14v14h-14z" fill="#efe6da" />
          <g className="intro-smoke">
            <circle cx="154" cy="20" r="4" fill="#e9ece9" />
            <circle cx="154" cy="20" r="4" fill="#e9ece9" />
            <circle cx="154" cy="20" r="4" fill="#e9ece9" />
          </g>
          <path d="M30 100h44M38 107h30M46 114h14M118 100h42M126 107h26M196 100h40M204 107h24M212 114h10" stroke="#e0825f" strokeWidth="2.4" strokeLinecap="round" opacity="0.5" />
        </svg>
        <div className="intro-action" ref={actionRef}>
          <svg viewBox="0 0 820 520">
            <g ref={boatRef}>
              <path d="M102 404c68 14 198 14 302 2l-12 24c-92 10-212 10-276-4z" fill="#8b959c" opacity="0.55" />
              {/* the ship's cat, sitting in the bow, waiting for its share */}
              <g data-part="cat" transform="translate(380 356)">
                <path data-part="cat-tail" d="M-12 1C-26 3-36-8-31-25" stroke="#142130" strokeWidth="5.5" fill="none" strokeLinecap="round" />
                <path d="M-13 8C-17-12-12-30-2-34C8-37 15-30 16-20C17-10 16 0 15 8z" fill="#142130" />
                <g data-part="cat-head" transform="rotate(14 5 -32)">
                  <ellipse cx="8" cy="-41" rx="11.5" ry="9.8" fill="#142130" />
                  <path d="M-1-47l-1-13 10 8zM12-50l8-11v15z" fill="#142130" />
                  <ellipse cx="13" cy="-42" rx="2.5" ry="3" fill="#efe6da" />
                  <ellipse cx="13.7" cy="-42" rx="0.9" ry="2.5" fill="#142130" />
                  <path d="M18-38l10-3M18-36.5l10 1" stroke="#142130" strokeWidth="0.9" strokeLinecap="round" />
                </g>
              </g>
              <path d="M52 330c68 16 248 22 368 24l-16 48c-104 10-234 10-302-4-22-18-40-46-50-68z" fill="#232e3a" />
              <path d="M74 350c86 12 226 16 340 18M90 372c90 10 210 14 318 14" stroke="#3a4655" strokeWidth="2" fill="none" />
              {/* her name; the team's test only counts data the models never saw */}
              <path id="hull-name" d="M90 366.5c90 10 210 14 318 14" fill="none" />
              <text className="intro-hull-name">
                <textPath href="#hull-name" startOffset="58%" textAnchor="middle">
                  Out of Sample
                </textPath>
              </text>
              <path d="M52 330c68 16 248 22 368 24" stroke="#4a5767" strokeWidth="3" fill="none" strokeLinecap="round" />
              <path d="M232 343v-9M226 334h12" stroke="#4a5767" strokeWidth="3" strokeLinecap="round" />
              {/* the fisherman: a navy figure in a knitted hat and scarf, standing */}
              <g data-part="fisherman" className="intro-fisherman">
                <path d="M264 288l-18 60M278 288l20 60" stroke="#1c2836" strokeWidth="15" strokeLinecap="round" />
                <path d="M270 222q16 32 46 24" stroke="#1c2836" strokeWidth="12" fill="none" strokeLinecap="round" />
                <path data-part="scarf" d="" stroke="#e0825f" strokeWidth="9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                <path data-part="scarf-stripes" d="" stroke="#f4f0ea" strokeWidth="9" fill="none" strokeDasharray="5 15" />
                <path d="M246 294c-6-30-2-70 16-86l18-2c16 10 22 46 16 88z" fill="#142130" />
                <path d="M284 218q16 28 38 20" stroke="#142130" strokeWidth="13" fill="none" strokeLinecap="round" />
                <path d="M254 207q16 9 34 0" stroke="#e0825f" strokeWidth="10" fill="none" strokeLinecap="round" />
                <g data-part="head">
                  <circle cx="270" cy="186" r="15" fill="#142130" />
                  <path d="M256 190C256 206 264 224 278 224C288 218 294 202 292 190C286 194 262 196 256 190z" fill="#f4f0ea" />
                  <path d="M252 181C252 160 288 158 289 180z" fill="#e0825f" />
                  <rect x="250" y="175" width="41" height="11" rx="5.5" fill="#c56f50" />
                  <circle data-part="bobble" cx="269" cy="158" r="7" fill="#f4f0ea" />
                  <ellipse cx="290.5" cy="190" rx="6.5" ry="5.2" fill="#eaa98e" />
                </g>
              </g>
              <g ref={rodRef} transform={`rotate(${ANGLE_REST} ${HANDS.x} ${HANDS.y})`}>
                <path ref={rodPathRef} d={rest.d} stroke="#142130" strokeWidth="4" fill="none" strokeLinecap="round" />
                <circle cx={HANDS.x - 12} cy={HANDS.y + 9} r="7" fill="#142130" />
              </g>
              <circle cx={HANDS.x} cy={HANDS.y} r="6.5" fill="#142130" />
            </g>
            <path ref={lineRef} d="" stroke="#142130" strokeWidth="1.4" fill="none" />
            {/* the signal: each tug pulses out from the rod tip */}
            <g data-part="signal" fill="none" stroke="#e0825f" strokeWidth="2.6" strokeLinecap="round">
              <path d="M-2.08-11.82A12 12 0 0 1 11.82-2.08" style={{ opacity: 0 }} />
              <path d="M-3.47-19.7A20 20 0 0 1 19.7-3.47" style={{ opacity: 0 }} />
              <path d="M-4.86-27.57A28 28 0 0 1 27.57-4.86" style={{ opacity: 0 }} />
            </g>
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
              <g data-part="fish-eye">
                <circle cx="14" cy="-5" r="3.8" fill="#f4f0ea" />
                <circle data-part="fish-pupil" cx="12.8" cy="-5.3" r="2.2" fill="#142130" />
                <clipPath id="fish-eye-clip">
                  <circle cx="14" cy="-5" r="3.8" />
                </clipPath>
                <g clipPath="url(#fish-eye-clip)">
                  <path data-part="fish-lid" d="M9-10h10v4.6q-5 .8-10 0z" fill="#8f9ba5" />
                </g>
              </g>
              <path d="M2 2q5 3.5 11 1" stroke="#6d7983" strokeWidth="1.5" fill="none" strokeLinecap="round" />
            </g>
          </svg>
        </div>
      </div>

      <div className="intro-copy" ref={copyRef}>
        <h1 id="intro-title" className="intro-title">
          Salmon Signal
        </h1>
      </div>

      {/* A gull on the title, in the salmon's two greys; JavaScript puts it on top of an l. */}
      <div className="intro-gull" data-part="gull" aria-hidden="true">
        <svg viewBox="0 0 100 84">
          <g data-part="gull-legs">
            <path d="M46 66l-1 15M56 66l-1 15" stroke="#eaa98e" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M45 80.5l-9 3h11zM55 80.5l-9 3h11z" fill="#eaa98e" />
          </g>
          {/* the far wing, behind the body, in flight */}
          <g data-part="gull-far" style={{ display: 'none' }}>
            <path d={GULL_WING} fill="#aeb8bf" />
            <path d={GULL_WING_TIP} fill="#142130" />
          </g>
          <path d={GULL_BODY} fill="#cdd4d8" />
          <g data-part="gull-folded">
            <path d="M33 40C44 31 64 38 78 51L72 58C56 61 40 55 33 40z" fill="#8f9ba5" />
            <path d="M70 52l28 14-25-5z" fill="#142130" />
          </g>
          <g data-part="gull-near" style={{ display: 'none' }}>
            <path d={GULL_WING} fill="#8f9ba5" />
            <path d={GULL_WING_TIP} fill="#142130" />
          </g>
          <g data-part="gull-head">
            <circle cx="25" cy="27" r="10.5" fill="#cdd4d8" />
            <path d="M15.5 25C10 25 5 26.5 1 30C0 31.5 1.5 32.5 3 32L16 31.5z" fill="#e0825f" />
            <path data-part="gull-beak" d="M16 31.5L3 32C5 34.5 10 35 16 34z" fill="#c56f50" />
            <circle cx="22.5" cy="24.5" r="1.9" fill="#142130" />
          </g>
        </svg>
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
          <span className="oslo-bars" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>{' '}
          Oslo
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
