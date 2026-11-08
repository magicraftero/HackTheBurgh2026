import { useEffect, useRef } from 'react';

/**
 * The farm game is its own static page in public/cockpit/. It sits in a frame so
 * its styles can't clash with the site's, and the frame grows to the game's full
 * height so the page keeps a single scrollbar.
 */
export function FarmGame() {
  const frameRef = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    let observer: ResizeObserver | undefined;

    const fitToGame = () => {
      const body = frame.contentDocument?.body;
      if (!body) return;
      const resize = () => {
        frame.style.height = `${Math.ceil(body.getBoundingClientRect().height)}px`;
      };
      observer?.disconnect();
      observer = new ResizeObserver(resize);
      observer.observe(body);
      resize();
    };

    frame.addEventListener('load', fitToGame);
    return () => {
      frame.removeEventListener('load', fitToGame);
      observer?.disconnect();
    };
  }, []);

  return (
    <iframe
      ref={frameRef}
      className="farm-game"
      src="cockpit/index.html"
      title="Run your own salmon farm: a game built on Norway's farm data"
      loading="lazy"
    />
  );
}
