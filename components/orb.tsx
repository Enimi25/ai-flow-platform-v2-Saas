"use client";

import { useEffect, useRef } from "react";
import s from "./orb.module.css";

/**
 * A sphere of points, drawn on a canvas and turned slowly.
 *
 * Points are brighter where the sphere's surface runs edge on to the camera,
 * which is what makes a scatter of dots read as a solid glowing shell rather
 * than noise. Colour is taken from the brand, warm at the top, cool at the
 * bottom, so the shape has a direction of light.
 */

type Point = { x: number; y: number; z: number };

const COUNT = 5200;

function sphere(count: number): Point[] {
  const points: Point[] = [];
  // golden angle spiral: even coverage without clumping at the poles
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i += 1) {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = golden * i;
    points.push({ x: Math.cos(theta) * radius, y, z: Math.sin(theta) * radius });
  }
  return points;
}

export function Orb({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const points = sphere(COUNT);

    let width = 0;
    let height = 0;
    let ratio = 1;

    const resize = () => {
      const box = canvas.getBoundingClientRect();
      ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = box.width;
      height = box.height;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    let visible = true;
    const watcher = new IntersectionObserver(
      ([entry]) => { visible = entry.isIntersecting; },
      { threshold: 0 },
    );
    watcher.observe(canvas);

    let frame = 0;
    let spin = 0;
    let tilt = -0.32;

    const draw = () => {
      const size = Math.min(width, height);
      const radius = size * 0.38;
      const cx = width / 2;
      const cy = height / 2;

      context.clearRect(0, 0, width, height);
      context.globalCompositeOperation = "lighter";

      const cosSpin = Math.cos(spin);
      const sinSpin = Math.sin(spin);
      const cosTilt = Math.cos(tilt);
      const sinTilt = Math.sin(tilt);

      for (const point of points) {
        // turn around the vertical axis, then lean the whole sphere back
        const x1 = point.x * cosSpin - point.z * sinSpin;
        const z1 = point.x * sinSpin + point.z * cosSpin;
        const y2 = point.y * cosTilt - z1 * sinTilt;
        const z2 = point.y * sinTilt + z1 * cosTilt;

        // perspective: points at the back sit closer to the centre and dim
        const depth = 1 / (2.6 - z2);
        const px = cx + x1 * radius * depth * 2.6;
        const py = cy + y2 * radius * depth * 2.6;

        // the shell reads as solid because the rim is brightest
        const rim = Math.pow(1 - Math.abs(z2), 2.6);
        const front = (z2 + 1) / 2;
        const alpha = (0.05 + rim * 1.25) * (0.3 + front * 0.7);
        if (alpha < 0.010) continue;

        // lime at the top of the shell, teal at the bottom
        const warm = (point.y + 1) / 2;
        const r = Math.round(70 + warm * 130);
        const g = Math.round(215 + warm * 35);
        const b = Math.round(170 - warm * 112);

        context.fillStyle = `rgba(${r},${g},${b},${alpha.toFixed(3)})`;
        const dot = (0.5 + rim * 2.1) * depth * 2.4;
        context.fillRect(px, py, dot, dot);
      }

      context.globalCompositeOperation = "source-over";
    };

    const tick = () => {
      if (visible) {
        spin += 0.0016;
        tilt = -0.32 + Math.sin(spin * 0.7) * 0.06;
        draw();
      }
      frame = requestAnimationFrame(tick);
    };

    if (reduced) {
      draw();
    } else {
      frame = requestAnimationFrame(tick);
    }

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      watcher.disconnect();
    };
  }, []);

  return (
    <div className={[s.wrap, className].filter(Boolean).join(" ")} aria-hidden="true">
      <canvas ref={canvasRef} className={s.canvas} />
      <div className={s.bloom} />
    </div>
  );
}
