"use client";

import { useEffect, useRef } from "react";
import s from "./scene.module.css";

/**
 * A hanging structure of light over a wet floor.
 *
 * Filaments fall from a ring above, drift, and are mirrored below the horizon
 * with the reflection blurred and dimmed. Colour is iridescent rather than
 * branded: the hue shifts along each strand, which is what makes the material
 * read as pearl instead of plastic.
 */

const STRANDS = 220;
const SEGMENTS = 44;
const HORIZON = 0.62;

const IRIDESCENT: [number, number, number][] = [
  [128, 116, 220],  // indigo
  [206, 142, 236],  // orchid
  [246, 168, 214],  // rose quartz
  [188, 226, 246],  // pale cyan
  [230, 226, 250],  // pearl
];

function shimmer(t: number): [number, number, number] {
  const clamped = ((t % 1) + 1) % 1;
  const span = clamped * (IRIDESCENT.length - 1);
  const i = Math.min(Math.floor(span), IRIDESCENT.length - 2);
  const k = span - i;
  const a = IRIDESCENT[i];
  const b = IRIDESCENT[i + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * k),
    Math.round(a[1] + (b[1] - a[1]) * k),
    Math.round(a[2] + (b[2] - a[2]) * k),
  ];
}

export function Scene({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const strands = Array.from({ length: STRANDS }, (_, i) => {
      const seed = i / STRANDS;
      const angle = seed * Math.PI * 2 * 1.618;
      return {
        angle,
        radius: 0.24 + Math.pow(seed, 0.7) * 0.72,
        drop: 0.34 + ((i * 37) % 100) / 100 * 0.5,
        sway: 0.4 + ((i * 61) % 100) / 100,
        phase: seed * 17.3,
        hue: seed * 1.6,
        weight: 0.35 + ((i * 23) % 100) / 100 * 0.9,
      };
    });

    let w = 0;
    let h = 0;
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

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

    const onMove = (event: PointerEvent) => {
      pointer.tx = (event.clientX / window.innerWidth - 0.5) * 2;
      pointer.ty = (event.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    let raf = 0;
    let time = 0;

    const strand = (
      cx: number, top: number, floor: number, scale: number,
      entry: (typeof strands)[number], mirrored: boolean,
    ) => {
      const spin = time * 0.09 + pointer.x * 0.22;
      const a = entry.angle + spin;
      const depth = (Math.cos(a) + 1) / 2;
      const hang = Math.sin(a) * entry.radius * scale * 0.86;
      const length = (floor - top) * entry.drop * (0.72 + depth * 0.45);

      ctx.beginPath();
      for (let i = 0; i <= SEGMENTS; i += 1) {
        const t = i / SEGMENTS;

        // strands leave the ring wide and gather toward the centre as they fall,
        // which is what makes the shape read as a chandelier and not a curtain
        const gather = 1 - Math.pow(t, 1.5) * (0.42 + entry.drop * 0.3);
        const swing =
          Math.sin(time * entry.sway + entry.phase + t * 2.4) * 16 * t * (0.5 + depth) +
          pointer.x * 18 * t;

        const px = cx + hang * gather + swing;
        const y0 = top + length * t;
        const py = mirrored ? floor + (floor - y0) * 0.72 : y0;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }

      const [r, g, b] = shimmer(entry.hue + depth * 0.35 + time * 0.03);
      const alpha = (0.05 + depth * 0.30) * (mirrored ? 0.30 : 1);
      ctx.strokeStyle = `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
      ctx.lineWidth = entry.weight * (0.4 + depth * 0.9) * (mirrored ? 0.8 : 1);
      ctx.stroke();
    };

    const draw = () => {
      pointer.x += (pointer.tx - pointer.x) * 0.05;
      pointer.y += (pointer.ty - pointer.y) * 0.05;

      const cx = w / 2 + pointer.x * 26;
      const floor = h * HORIZON;
      const top = h * 0.08 + pointer.y * 12;
      const scale = Math.min(w, h * 1.5) * 0.5;

      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";
      ctx.lineCap = "round";

      // reflection first, so the real structure sits on top of it
      for (const entry of strands) strand(cx, top, floor, scale, entry, true);
      for (const entry of strands) strand(cx, top, floor, scale, entry, false);

      // the ring the strands hang from
      for (let ring = 0; ring < 3; ring += 1) {
        const spread = 0.78 - ring * 0.055;
        ctx.beginPath();
        ctx.ellipse(cx, top + ring * 9, scale * spread, scale * spread * 0.17, 0, 0, Math.PI * 2);
        const [rr, rg, rb] = shimmer(time * 0.05 + ring * 0.18);
        ctx.strokeStyle = `rgba(${rr},${rg},${rb},${(0.30 - ring * 0.07).toFixed(2)})`;
        ctx.lineWidth = 1.6 - ring * 0.3;
        ctx.stroke();
      }

      // the pool of light the whole thing hangs over
      const pool = ctx.createRadialGradient(cx, floor, 0, cx, floor, scale * 0.9);
      pool.addColorStop(0, "rgba(246, 168, 214, .16)");
      pool.addColorStop(0.45, "rgba(128, 116, 220, .09)");
      pool.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = pool;
      ctx.beginPath();
      ctx.ellipse(cx, floor, scale * 0.9, scale * 0.2, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.globalCompositeOperation = "source-over";
    };

    const tick = () => {
      if (onScreen) {
        time += 0.007;
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
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return (
    <div className={[s.wrap, className].filter(Boolean).join(" ")} aria-hidden="true">
      <canvas ref={canvasRef} className={s.canvas} />
      <div className={s.floor} />
      <div className={s.haze} />
      <div className={s.weave} />
    </div>
  );
}
