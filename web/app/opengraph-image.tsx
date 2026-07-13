import { ImageResponse } from 'next/og';

// Social share card: owl mascot + name on the brand background.
export const alt = 'Behavioral Interview Coach: voice mock interviews with rubric-graded feedback';
export const size = {
  width: 1200,
  height: 628,
};
export const contentType = 'image/png';

const INDIGO = '#4f46e5';
const INDIGO_DARK = '#3d36c4';
const PAPER = '#faf8f2';
const INK = '#26233f';
const AMBER = '#f59e0b';

export default async function Image() {
  return new ImageResponse(
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: PAPER,
        gap: 28,
      }}
    >
      <svg width="200" height="200" viewBox="0 0 120 120" fill="none">
        <path d="M30 30 L38 12 L48 26 Z" fill={INDIGO} />
        <path d="M90 30 L82 12 L72 26 Z" fill={INDIGO} />
        <ellipse cx="60" cy="66" rx="42" ry="46" fill={INDIGO} />
        <path d="M20 60 q-6 22 12 34 q-2-18 0-30 Z" fill={INDIGO_DARK} />
        <path d="M100 60 q6 22 -12 34 q2-18 0-30 Z" fill={INDIGO_DARK} />
        <ellipse cx="60" cy="80" rx="26" ry="27" fill={PAPER} />
        <circle cx="42" cy="46" r="17" fill={PAPER} />
        <circle cx="78" cy="46" r="17" fill={PAPER} />
        <circle cx="42" cy="46" r="13.5" stroke={INK} strokeWidth="3" fill="none" />
        <circle cx="78" cy="46" r="13.5" stroke={INK} strokeWidth="3" fill="none" />
        <path d="M55.5 46 h9" stroke={INK} strokeWidth="3" strokeLinecap="round" />
        <circle cx="42" cy="46" r="6" fill={INK} />
        <circle cx="78" cy="46" r="6" fill={INK} />
        <circle cx="44" cy="44" r="2" fill={PAPER} />
        <circle cx="80" cy="44" r="2" fill={PAPER} />
        <path d="M60 54 L54 62 Q60 68 66 62 Z" fill={AMBER} />
      </svg>
      <div
        style={{
          display: 'flex',
          fontSize: 64,
          fontWeight: 700,
          color: INK,
          letterSpacing: -1.5,
        }}
      >
        Behavioral Interview Coach
      </div>
      <div
        style={{
          display: 'flex',
          fontSize: 28,
          color: '#6b6885',
        }}
      >
        Voice mock interviews: real questions, probing follow-ups, rubric-graded feedback
      </div>
    </div>,
    {
      ...size,
    }
  );
}
