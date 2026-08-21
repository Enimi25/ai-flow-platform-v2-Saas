import type { CSSProperties } from "react";
import s from "./strand.module.css";

type StrandProps = {
  rungs?: number;
  radius?: number;
  gap?: number;
  step?: number;
  /** degrees the helix turns across the driving scroll range */
  spin?: number;
  idle?: boolean;
  className?: string;
};

export default function Strand({
  rungs = 34,
  radius = 128,
  gap = 22,
  step = 18,
  spin = 380,
  idle = true,
  className,
}: StrandProps) {
  const vars = {
    "--n": rungs,
    "--r": `${radius}px`,
    "--gap": `${gap}px`,
    "--step": `${step}deg`,
    "--spin": `${spin}deg`,
  } as CSSProperties;

  return (
    <div className={[s.clip, className].filter(Boolean).join(" ")} aria-hidden="true">
      <div className={s.stage} style={vars}>
        <div className={s.turn} data-strand-turn data-spin={spin}>
          <div className={idle ? s.spin : undefined}>
            {Array.from({ length: rungs }, (_, i) => (
              <span
                key={i}
                className={s.rung}
                data-beat={i % 6 === 0 ? "1" : undefined}
                style={{ "--i": i } as CSSProperties}
              />
            ))}
          </div>
        </div>
      </div>
      <div className={s.fog} />
    </div>
  );
}
