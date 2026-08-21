"use client";

import { useEffect, useRef } from "react";
import s from "./orb.module.css";

/**
 * A ring of light: hundreds of filaments traced around a sphere, each pushed
 * off course by layered turbulence and drawn additively.
 *
 * Points would read as a wireframe globe. Overlapping strokes at low opacity
 * read as energy, because brightness accumulates where filaments cross and
 * falls away where they thin out, which is what makes the rim glow.
 */

const FILAMENTS = 170;
const SEGMENTS = 150;

/**
 * The ring sweeps through four colours rather than one, so it reads as light
 * with a direction instead of a flat green ball. Cool at the bottom, hot at
 * the top, staying inside the brand's own range.
 */
const RAMP: [number, number, number][] = [
  [34, 168, 210],   // deep cyan
  [62, 207, 178],   // teal
  [150, 235, 110],  // spring green
  [195, 245, 60],   // lime
  [232, 214, 92],   // warm gold
];

function ramp(t: number): [number, number, number] {
  const clamped = ((t % 1) + 1) % 1;
  const span = clamped * (RAMP.length - 1);
  const index = Math.min(Math.floor(span), RAMP.length - 2);
  const mix = span - index;
  const a = RAMP[index];
  const b = RAMP[index + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * mix),
    Math.round(a[1] + (b[1] - a[1]) * mix),
    Math.round(a[2] + (b[2] - a[2]) * mix),
  ];
}

/** Cheap layered noise. No library, and smooth enough at this scale. */
function wobble(a: number, b: number, t: number) {
  return (
    Math.sin(a * 2.1 + t) * 0.55 +
    Math.sin(a * 4.7 - b * 1.3 + t * 1.4) * 0.28 +
    Math.sin(a * 9.3 + b * 2.7 - t * 0.8) * 0.13 +
    Math.sin(b * 6.1 + t * 1.9) * 0.09
  );
}

export function Orb({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // each filament gets a fixed tilt and phase so the ring keeps its character
    const strands = Array.from({ length: FILAMENTS }, (_, i) => {
      const seed = i / FILAMENTS;
      return {
        tilt: (seed - 0.5) * Math.PI * 0.96,
        roll: seed * Math.PI * 2 * 3.7,
        phase: seed * 11.3,
        weight: 0.35 + (1 - Math.abs(seed - 0.5) * 2) * 0.8,
        hue: seed,
      };
    });

    let w = 0;
    let h = 0;

    const resize = () => {
      const box = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      w = box.width;
      h = box.height;
      canvas.width = Math.round(w * ratio);
      canvas.height = Math.round(h * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    resize();
    const sizeWatcher = new ResizeObserver(resize);
    sizeWatcher.observe(canvas);

    let onScreen = true;
    const viewWatcher = new IntersectionObserver(
      ([entry]) => { onScreen = entry.isIntersecting; },
      { threshold: 0 },
    );
    viewWatcher.observe(canvas);

    let raf = 0;
    let time = 0;

    const draw = () => {
      const size = Math.min(w, h);
      const radius = size * 0.29;
      const cx = w / 2;
      const cy = h / 2;

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      ctx.lineCap = "round";

      for (const strand of strands) {
        const cosT = Math.cos(strand.tilt);
        const sinT = Math.sin(strand.tilt);
        const spin = time * 0.16 + strand.roll;

        ctx.beginPath();
        let bright = 0;

        for (let i = 0; i <= SEGMENTS; i += 1) {
          const u = (i / SEGMENTS) * Math.PI * 2;

          // a great circle, then pushed out of shape by turbulence
          const push = 1 + wobble(u, strand.phase, time * 0.55) * 0.13;
          const x0 = Math.cos(u) * push;
          const y0 = Math.sin(u) * push * cosT;
          const z0 = Math.sin(u) * push * sinT;

          const x1 = x0 * Math.cos(spin) - z0 * Math.sin(spin);
          const z1 = x0 * Math.sin(spin) + z0 * Math.cos(spin);

          const depth = 1 / (2.35 - z1 * 0.9);
          const px = cx + x1 * radius * depth * 2.35;
          const py = cy + y0 * radius * depth * 2.35;

          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);

          bright += (z1 + 1) / 2;
        }

        // filaments facing the camera are dimmer, the rim is where light piles up
        const facing = bright / (SEGMENTS + 1);
        const glow = 0.10 + Math.pow(1 - Math.abs(facing - 0.5) * 2, 0.6) * 0.16;

        const [r, g, b] = ramp(strand.hue + Math.sin(time * 0.25) * 0.06);
        ctx.strokeStyle = `rgba(${r},${g},${b},${glow.toFixed(3)})`;
        ctx.lineWidth = strand.weight * (0.5 + facing * 0.9);
        ctx.stroke();
      }

      ctx.globalCompositeOperation = "source-over";
    };

    const tick = () => {
      if (onScreen) {
        time += 0.006;
        draw();
      }
      raf = requestAnimationFrame(tick);
    };

    if (reduced) draw();
    else raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      sizeWatcher.disconnect();
      viewWatcher.disconnect();
    };
  }, []);

  return (
    <div className={[s.wrap, className].filter(Boolean).join(" ")} aria-hidden="true">
      <canvas ref={canvasRef} className={s.canvas} />
      <div className={s.bloom} />
      <div className={s.core} />
    </div>
  );
}
