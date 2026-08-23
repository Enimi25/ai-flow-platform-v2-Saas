"use client";

import { useEffect, useState } from "react";
import type { Mood } from "./moods";
import s from "./mascot.module.css";

/**
 * Flo on screen.
 *
 * The character is artwork, not geometry: a rendered PNG with a transparent
 * background, dropped in at /public/flo/. Hand-authored SVG cannot reach that
 * finish, so the drawn dalmatian is only the fallback for when the art is
 * missing. Everything that makes Flo feel alive — the breathing bob, the cocked
 * head, the jaw moving while the voice runs — is CSS on top of the image, so it
 * works the same either way.
 *
 * Two frames are enough for speech: mouth shut and mouth open, alternated on a
 * short cycle. Give it only flo.png and it falls back to a nod.
 */
const REST = "/flo/flo.png";
const TALK = "/flo/flo-talking.png";

export function Mascot({
  mood = "idle",
  size = 150,
  className,
  open,
  onClick,
}: {
  mood?: Mood;
  size?: number;
  className?: string;
  open?: boolean;
  onClick?: () => void;
}) {
  const [art, setArt] = useState<"unknown" | "yes" | "no">("unknown");
  const [hasTalkFrame, setHasTalkFrame] = useState(false);
  const [talkFrame, setTalkFrame] = useState(false);
  const [idlePose, setIdlePose] = useState<"rest" | "curious" | "greeting">("rest");

  useEffect(() => {
    let live = true;
    const probe = new Image();
    probe.onload = () => live && setArt("yes");
    probe.onerror = () => live && setArt("no");
    probe.src = REST;

    // The second frame is optional. Without it Flo still breathes and nods; he
    // just does not open his mouth. Treating it as required would hide him
    // entirely over one missing file.
    const mouth = new Image();
    mouth.onload = () => live && setHasTalkFrame(true);
    mouth.src = TALK;

    return () => {
      live = false;
    };
  }, []);

  // the two-frame mouth, only while the voice is actually running
  useEffect(() => {
    if (mood !== "speaking" || art !== "yes" || !hasTalkFrame) {
      setTalkFrame(false);
      return;
    }
    const timer = window.setInterval(() => setTalkFrame((f) => !f), 165);
    return () => window.clearInterval(timer);
  }, [mood, art, hasTalkFrame]);

  // A small pose change keeps Flo from reading as a static sticker while the
  // chat is waiting. The actual image stays crisp; CSS supplies the motion.
  useEffect(() => {
    if (mood !== "idle" || art !== "yes") return;
    const poses: Array<"rest" | "curious" | "greeting"> = ["rest", "curious", "greeting"];
    const timer = window.setInterval(() => {
      setIdlePose((current) => poses[(poses.indexOf(current) + 1) % poses.length]);
    }, 5600);
    return () => window.clearInterval(timer);
  }, [mood, art]);

  if (art === "no") return null;

  return (
    <span
      className={[s.mascot, className].filter(Boolean).join(" ")}
      data-mood={mood}
      data-pose={mood === "idle" ? idlePose : mood}
      data-open={open ? "true" : "false"}
      data-pending={art === "unknown" ? "true" : undefined}
      style={{ width: Math.round(size * 0.72), height: size }}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => (e.key === "Enter" || e.key === " ") && onClick() : undefined}
      aria-label={onClick ? "Open the chat with Flo" : undefined}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={talkFrame && hasTalkFrame ? TALK : REST} alt="" draggable={false} onError={() => setArt("no")} />
    </span>
  );
}
