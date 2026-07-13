// The app mascot: a calm, bespectacled owl interviewer. Hand-drawn SVG so
// there are no external assets or license questions. Colors ride the theme
// tokens (--primary etc.) and adapt to dark mode automatically.
export function OwlMascot({ size = 80, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      role="img"
      aria-label="The interview coach owl"
      className={className}
    >
      {/* ear tufts */}
      <path d="M30 30 L38 12 L48 26 Z" fill="var(--primary)" />
      <path d="M90 30 L82 12 L72 26 Z" fill="var(--primary)" />
      {/* body */}
      <ellipse cx="60" cy="66" rx="42" ry="46" fill="var(--primary)" />
      {/* wings */}
      <path
        d="M20 60 q-6 22 12 34 q-2-18 0-30 Z"
        fill="color-mix(in oklab, var(--primary) 78%, black)"
      />
      <path
        d="M100 60 q6 22 -12 34 q2-18 0-30 Z"
        fill="color-mix(in oklab, var(--primary) 78%, black)"
      />
      {/* belly */}
      <ellipse cx="60" cy="80" rx="26" ry="27" fill="var(--card)" />
      {/* belly feather rows */}
      <path
        d="M44 74 q4 5 8 0 q4 5 8 0 q4 5 8 0 q4 5 8 0 M48 86 q4 5 8 0 q4 5 8 0 q4 5 8 0"
        stroke="color-mix(in oklab, var(--primary) 30%, transparent)"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      {/* face disc */}
      <circle cx="42" cy="46" r="17" fill="var(--card)" />
      <circle cx="78" cy="46" r="17" fill="var(--card)" />
      {/* glasses */}
      <circle cx="42" cy="46" r="13.5" stroke="var(--foreground)" strokeWidth="3" fill="none" />
      <circle cx="78" cy="46" r="13.5" stroke="var(--foreground)" strokeWidth="3" fill="none" />
      <path d="M55.5 46 h9" stroke="var(--foreground)" strokeWidth="3" strokeLinecap="round" />
      {/* eyes */}
      <circle cx="42" cy="46" r="6" fill="var(--foreground)" />
      <circle cx="78" cy="46" r="6" fill="var(--foreground)" />
      <circle cx="44" cy="44" r="2" fill="var(--card)" />
      <circle cx="80" cy="44" r="2" fill="var(--card)" />
      {/* beak */}
      <path d="M60 54 L54 62 Q60 68 66 62 Z" fill="#f59e0b" />
      {/* feet */}
      <path
        d="M48 111 q2 4 5 0 M52 112 q2 4 5 0 M63 112 q2 4 5 0 M67 111 q2 4 5 0"
        stroke="#f59e0b"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
