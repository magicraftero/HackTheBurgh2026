// Small line icons. Decorative: every icon sits next to a text label.

type P = { size?: number; className?: string };

const svgProps = (size = 16, className?: string) =>
  ({
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2.2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
    focusable: false,
    className: `ico${className ? ` ${className}` : ''}`,
  }) as const;

export const IconCheck = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M5 12.5l4.2 4.2L19 7" />
  </svg>
);

export const IconCross = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </svg>
);

export const IconClose = IconCross;

export const IconClock = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </svg>
);

export const IconHalf = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5a8.5 8.5 0 0 1 0 17z" fill="currentColor" stroke="none" />
  </svg>
);

export const IconArrow = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const IconPlus = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const IconAlert = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M12 4l9 16H3z" />
    <path d="M12 10v4M12 17.5v.01" />
  </svg>
);

export const IconRefresh = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M20 11a8 8 0 1 0-2.3 5.7" />
    <path d="M20 5v6h-6" />
  </svg>
);

export const IconPlay = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
  </svg>
);

export const IconPause = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <path d="M8.5 5.5v13M15.5 5.5v13" strokeWidth={3.2} />
  </svg>
);

export const IconSearch = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <circle cx="10.5" cy="10.5" r="6" />
    <path d="M15 15l5 5" />
  </svg>
);

/** The fishing reel on the "Reel in" button. */
export const IconReel = ({ size, className }: P) => (
  <svg {...svgProps(size, className)}>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="2.2" />
    <path d="M12 12l4.5-4.5" />
  </svg>
);

/** The brand mark: a fishing hook. */
export const HookMark = ({ size = 20, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
    <circle cx="14.5" cy="3.6" r="1.9" stroke={color} strokeWidth="2" />
    <path d="M14.5 5.5v9.2a4.6 4.6 0 0 1-9.2 0v-1.9l2.6 2.4" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

/** The wordmark's salmon. */
export const FishMark = ({ size = 30 }: { size?: number }) => (
  <svg width={size} height={size * 0.62} viewBox="0 0 50 31" aria-hidden="true" focusable="false">
    <path d="M2 15.5C8 6 20 2.5 31 5.5c4.5 1.3 8 4.4 10.5 10-2.5 5.6-6 8.7-10.5 10C20 28.5 8 25 2 15.5z" fill="#f27a5e" />
    <path d="M40 15.5l9-8v16z" fill="#f27a5e" />
    <path d="M20 9c3 4 3 9 0 13" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.7" />
    <circle cx="10.5" cy="13.5" r="2.2" fill="#0b0b0c" />
  </svg>
);
