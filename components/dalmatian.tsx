import s from "./dalmatian.module.css";

export type Mood = "idle" | "listening" | "thinking" | "speaking";

/**
 * The mascot. Drawn by hand because the brief asks for this specific character
 * and no illustration of it exists in the project.
 */
export function Dalmatian({ mood = "idle", size = 44 }: { mood?: Mood; size?: number }) {
  return (
    <svg
      className={s.dog}
      data-mood={mood}
      width={size}
      height={size}
      viewBox="0 0 96 96"
      role="img"
      aria-label="AI FLOW assistant"
    >
      <defs>
        <radialGradient id="dalCoat" cx="38%" cy="30%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#dfe7e2" />
        </radialGradient>
        <linearGradient id="dalCollar" x1="0" y1="0" x2="1" y2="0">
          <stop offset="4%" stopColor="var(--accent)" />
          <stop offset="96%" stopColor="var(--accent-2)" />
        </linearGradient>
      </defs>

      <g className={s.head}>
        <g className={s.earLeft}>
          <ellipse cx="21" cy="46" rx="11" ry="20" fill="#16211d" />
        </g>
        <g className={s.earRight}>
          <ellipse cx="75" cy="46" rx="11" ry="20" fill="#16211d" />
        </g>

        <ellipse cx="48" cy="46" rx="30" ry="28" fill="url(#dalCoat)" />

        {/* coat markings */}
        <circle cx="33" cy="30" r="4.4" fill="#16211d" opacity=".82" />
        <circle cx="63" cy="33" r="3.2" fill="#16211d" opacity=".7" />
        <circle cx="27" cy="53" r="2.6" fill="#16211d" opacity=".55" />
        <circle cx="69" cy="55" r="3.6" fill="#16211d" opacity=".62" />

        <g className={s.eyes}>
          <ellipse cx="38" cy="45" rx="4.1" ry="4.6" fill="#16211d" />
          <ellipse cx="58" cy="45" rx="4.1" ry="4.6" fill="#16211d" />
          <circle cx="39.4" cy="43.4" r="1.4" fill="#ffffff" />
          <circle cx="59.4" cy="43.4" r="1.4" fill="#ffffff" />
        </g>

        <ellipse cx="48" cy="57" rx="5.4" ry="4" fill="#16211d" />
        <g className={s.muzzle}>
          <ellipse cx="48" cy="65" rx="7.5" ry="4.5" fill="#16211d" />
        </g>

        <path
          className={s.collar}
          d="M24 68 Q48 80 72 68"
          stroke="url(#dalCollar)"
          strokeWidth="7"
          strokeLinecap="round"
          fill="none"
        />
      </g>
    </svg>
  );
}
