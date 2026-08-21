"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import s from "./spiral.module.css";

gsap.registerPlugin(ScrollTrigger);

/**
 * Cards hung on a helix. Scroll turns the coil and walks it downward, so a card
 * swings out of the dark, faces the reader, and drops away behind the next one.
 *
 * The maths is a helix in three dimensions projected by CSS: each card gets an
 * angle and a height, and the whole rig is rotated as the section is scrubbed.
 */

const TURNS = 2.2;

const CARDS = [
  { title: "Website agent", note: "Answers on your site in seconds" },
  { title: "Messenger", note: "Replies to Facebook conversations" },
  { title: "Instagram", note: "Direct messages and comments" },
  { title: "WhatsApp", note: "For verified businesses" },
  { title: "Lead capture", note: "Name, phone, email, source" },
  { title: "Calendar", note: "Booked straight into your day" },
  { title: "Content factory", note: "Posts and reels, written and scheduled" },
  { title: "One workspace", note: "Everything in a single place" },
];

export function Spiral() {
  const rail = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const coil = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!rail.current || !stage.current || !coil.current) return;

    const section = rail.current;
    section.dataset.enhanced = "true";

    const ctx = gsap.context(() => {
      const cards = gsap.utils.toArray<HTMLElement>(`.${s.card}`);
      const radius = Math.min(window.innerWidth * 0.34, 460);
      const rise = 190;

      const place = (progress: number) => {
        cards.forEach((card, i) => {
          const t = i / cards.length;
          const angle = (t * TURNS + progress * TURNS) * Math.PI * 2;
          const y = (t - progress) * cards.length * rise;

          const x = Math.sin(angle) * radius;
          const z = Math.cos(angle) * radius;

          // face the reader, lean with the coil
          const facing = (z / radius + 1) / 2;
          card.style.transform =
            `translate3d(${x}px, ${y}px, ${z}px) rotateY(${-angle}rad) rotateX(${(0.5 - facing) * 8}deg)`;
          card.style.opacity = String(0.12 + facing * 0.88);
          card.style.zIndex = String(Math.round(facing * 100));
        });
      };

      place(0);

      gsap.to(
        {},
        {
          ease: "none",
          scrollTrigger: {
            trigger: section,
            start: "top top",
            end: () => `+=${window.innerHeight * 4}`,
            pin: stage.current,
            scrub: 0.6,
            invalidateOnRefresh: true,
            onUpdate: (self) => place(self.progress),
          },
        },
      );
    }, rail);

    document.fonts?.ready.then(() => ScrollTrigger.refresh());

    return () => {
      ctx.revert();
      delete section.dataset.enhanced;
    };
  }, []);

  return (
    <section ref={rail} className={s.rail} id="how-it-works">
      <div ref={stage} className={s.stage}>
        <div className={s.head}>
          <p className={s.eyebrow}>What are you looking for?</p>
          <h2 className={s.title}>Every channel, one agent.</h2>
        </div>

        <div className={s.space}>
          <div ref={coil} className={s.coil}>
            {CARDS.map((card) => (
              <article key={card.title} className={s.card}>
                <div className={s.face}>
                  <b>{card.title}</b>
                  <span>{card.note}</span>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
