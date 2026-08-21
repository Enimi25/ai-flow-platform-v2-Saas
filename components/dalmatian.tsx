import s from "./dalmatian.module.css";

export type Mood = "idle" | "listening" | "thinking" | "speaking";

/**
 * Flo, the mascot: a sitting dalmatian pup, head cocked, one ear flipped back
 * over the skull, tongue out. Original geometry — the cartoon dalmatian
 * everyone pictures belongs to Disney, and this ships on customer sites.
 *
 * One drawing, two crops. "full" is the whole pup for the launcher; "bust"
 * reframes the same paths on the head for the 44px avatar in the panel header.
 * That 44px sets the floor for detail: no linework thinner than about a pixel
 * on screen, ears well clear of the skull, one solid nose. The plate behind is
 * light because the spots are near-black and would vanish on --bg.
 */
export function Dalmatian({
  mood = "idle",
  size = 44,
  variant = "bust",
}: {
  mood?: Mood;
  size?: number;
  variant?: "bust" | "full";
}) {
  const full = variant === "full";

  return (
    <svg
      className={s.dog}
      data-mood={mood}
      data-variant={variant}
      width={full ? Math.round(size * 0.84) : size}
      height={size}
      viewBox={full ? "0 0 200 240" : "46 12 146 140"}
      role="img"
      aria-label="Flo, the AI FLOW assistant"
    >
      <defs>
        <radialGradient id="dalPlate" cx="30%" cy="20%" r="98%">
          <stop offset="0%" stopColor="#f6fcf4" />
          <stop offset="100%" stopColor="#cbe3d3" />
        </radialGradient>
        <radialGradient id="dalCoat" cx="34%" cy="24%" r="92%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#e2ebe6" />
        </radialGradient>
        <radialGradient id="dalIris" cx="34%" cy="28%" r="84%">
          <stop offset="0%" stopColor="#e0a659" />
          <stop offset="58%" stopColor="#a86a2c" />
          <stop offset="100%" stopColor="#5c3714" />
        </radialGradient>
        <linearGradient id="dalTongue" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ff9db3" />
          <stop offset="100%" stopColor="#e9647f" />
        </linearGradient>
        <linearGradient id="dalScarf" x1="0" y1="0" x2="1" y2="1">
          <stop offset="4%" stopColor="var(--accent)" />
          <stop offset="96%" stopColor="var(--accent-2)" />
        </linearGradient>
        <radialGradient id="dalInner" cx="40%" cy="40%" r="80%">
          <stop offset="0%" stopColor="#f0a9ab" />
          <stop offset="100%" stopColor="#c8767e" />
        </radialGradient>
      </defs>

      {!full && <circle cx="112" cy="80" r="72" fill="url(#dalPlate)" />}

      {full && (
        <g className={s.tail}>
          <path
            d="M76 198 C48 202 26 184 30 158 C32 145 40 137 49 134"
            stroke="url(#dalCoat)" strokeWidth="15" strokeLinecap="round" fill="none"
          />
          <circle cx="34" cy="168" r="4.6" fill="#1d2a24" />
          <circle cx="45" cy="140" r="3.6" fill="#1d2a24" />
        </g>
      )}

      {full && (
        <g className={s.body}>
          {/* haunch first, then the chest overlaps it: that read is what makes
              the pose say "sitting" rather than "standing side-on" */}
          <ellipse cx="74" cy="180" rx="31" ry="33" fill="#dde7e1" />
          <ellipse cx="58" cy="212" rx="17" ry="9.5" fill="#dde7e1" />

          <ellipse cx="112" cy="172" rx="38" ry="42" fill="url(#dalCoat)" />

          <path d="M92 176 C88 194 88 210 90 220 L110 220 C111 208 110 192 112 176 Z" fill="url(#dalCoat)" />
          <path d="M124 178 C121 196 121 210 123 220 L143 220 C144 208 143 194 145 178 Z" fill="url(#dalCoat)" />
          <ellipse cx="100" cy="221" rx="12" ry="7.5" fill="#ffffff" />
          <ellipse cx="133" cy="221" rx="12" ry="7.5" fill="#ffffff" />
          <path
            d="M96 217 L96 224 M104 217 L104 224 M129 217 L129 224 M137 217 L137 224"
            stroke="rgba(20,34,28,.22)" strokeWidth="1.6" strokeLinecap="round"
          />

          <circle cx="98" cy="152" r="7" fill="#1d2a24" />
          <circle cx="130" cy="166" r="7.6" fill="#1d2a24" />
          <circle cx="88" cy="188" r="5.4" fill="#1d2a24" />
          <circle cx="142" cy="192" r="5.8" fill="#1d2a24" />
          <circle cx="112" cy="200" r="4.4" fill="#1d2a24" />
          <circle cx="66" cy="166" r="6" fill="#1d2a24" opacity=".55" />
          <circle cx="80" cy="198" r="4.2" fill="#1d2a24" opacity=".5" />
        </g>
      )}

      <g className={s.head}>
        {/* the ear that hangs, on the low side of the tilt */}
        <g className={s.earLeft}>
          <path
            d="M80 54 C58 52 45 76 47 102 C49 122 65 128 75 118 C67 96 70 68 80 54 Z"
            fill="url(#dalCoat)" stroke="rgba(20,34,28,.13)" strokeWidth="1.4"
          />
          <circle cx="59" cy="86" r="6.2" fill="#1d2a24" />
          <circle cx="68" cy="108" r="4" fill="#1d2a24" />
        </g>

        {/* and the one flipped back over the skull — the whole reason a puppy
            reads as a puppy and not a small dog */}
        <g className={s.earRight}>
          <path
            d="M138 46 C154 22 180 16 189 31 C197 45 179 69 156 76 C145 79 136 68 138 46 Z"
            fill="url(#dalCoat)" stroke="rgba(20,34,28,.13)" strokeWidth="1.4"
          />
          <path
            d="M146 50 C158 34 176 28 182 38 C188 48 171 64 156 68 C148 70 144 62 146 50 Z"
            fill="url(#dalInner)"
          />
          <circle cx="149" cy="64" r="4.6" fill="#1d2a24" />
          <circle cx="170" cy="26" r="3.6" fill="#1d2a24" />
        </g>

        <ellipse
          cx="108" cy="74" rx="45" ry="42"
          fill="url(#dalCoat)"
          stroke="rgba(20,34,28,.13)" strokeWidth="1.4"
        />

        <circle cx="76" cy="44" r="7.4" fill="#1d2a24" />
        <circle cx="129" cy="98" r="4.6" fill="#1d2a24" opacity=".7" />

        {/* brows do the acting: without them the face is blank at any size */}
        <g className={s.brows}>
          <path d="M80 47 C86 40 97 40 103 46" stroke="#1d2a24" strokeWidth="5.6" strokeLinecap="round" fill="none" />
          <path d="M117 43 C123 37 133 38 138 45" stroke="#1d2a24" strokeWidth="5.6" strokeLinecap="round" fill="none" />
        </g>

        <g className={s.eyes}>
          <ellipse cx="92" cy="70" rx="12" ry="13.5" fill="#ffffff" stroke="#1d2a24" strokeWidth="1.8" />
          <ellipse cx="124" cy="68" rx="12" ry="13.5" fill="#ffffff" stroke="#1d2a24" strokeWidth="1.8" />
          <circle cx="93" cy="72" r="7.6" fill="url(#dalIris)" />
          <circle cx="125" cy="70" r="7.6" fill="url(#dalIris)" />
          <circle cx="93" cy="72.5" r="4" fill="#14100f" />
          <circle cx="125" cy="70.5" r="4" fill="#14100f" />
          <circle cx="89.4" cy="67.6" r="3.2" fill="#ffffff" />
          <circle cx="121.4" cy="65.6" r="3.2" fill="#ffffff" />
          <circle cx="96.2" cy="77" r="1.6" fill="#ffffff" opacity=".7" />
          <circle cx="128.2" cy="75" r="1.6" fill="#ffffff" opacity=".7" />
        </g>

        <ellipse cx="108" cy="96" rx="28" ry="19" fill="#ffffff" stroke="rgba(20,34,28,.1)" strokeWidth="1.2" />

        <g className={s.jaw}>
          <path d="M88 99 C91 116 127 116 129 99 C120 105 96 105 88 99 Z" fill="#6e2f39" />
          <path
            className={s.tongue}
            d="M100 104 C95 104 91 117 96 127 C101 136 117 134 118 122 C119 111 115 104 111 104 Z"
            fill="url(#dalTongue)"
          />
          <path d="M108 112 L108 128" stroke="#cf5670" strokeWidth="1.8" strokeLinecap="round" opacity=".75" />
        </g>

        <path
          d="M108 76 C117 76 123.5 80 123.5 85.5 C123.5 91 116 95.4 108 95.4
             C100 95.4 92.5 91 92.5 85.5 C92.5 80 99 76 108 76 Z"
          fill="#14100f"
        />
        <ellipse cx="102" cy="81.4" rx="3.6" ry="2.3" fill="#ffffff" opacity=".4" />
      </g>

      {/* the scarf carries the brand, so it takes the gradient rather than red */}
      <g className={s.scarf}>
        <path d="M78 114 C94 140 126 140 142 114 C126 128 94 128 78 114 Z" fill="url(#dalScarf)" />
        <path d="M70 122 C62 132 59 144 65 149 L78 134 Z" fill="url(#dalScarf)" opacity=".92" />
        <path d="M76 127 C70 139 69 148 75 152 L84 136 Z" fill="url(#dalScarf)" opacity=".8" />
        <ellipse cx="76" cy="117" rx="8.5" ry="7.5" fill="url(#dalScarf)" />
      </g>
    </svg>
  );
}
