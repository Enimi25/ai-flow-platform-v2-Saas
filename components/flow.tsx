"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Strand from "./strand";
import s from "./flow.module.css";

gsap.registerPlugin(ScrollTrigger);

const STAGES = [
  {
    title: "A customer writes",
    body: "Someone messages your website, Messenger, Instagram, or WhatsApp. Any hour, any language.",
  },
  {
    title: "The agent answers",
    body: "It replies in seconds, answers the real question, and finds out what the customer actually wants.",
  },
  {
    title: "The lead is kept",
    body: "Name, phone, email, source, and the full message land in your sheet before the chat ends.",
  },
  {
    title: "The slot is booked",
    body: "The agent writes the appointment straight into your calendar and follows up if nobody shows.",
  },
];

export default function Flow() {
  const rail = useRef<HTMLElement>(null);
  const sticky = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!rail.current || !sticky.current) return;

    // Switch to the pinned layout before the timeline is built, otherwise
    // ScrollTrigger measures the static heights and the pin lasts zero pixels.
    const section = rail.current;
    section.dataset.enhanced = "true";

    const ctx = gsap.context(() => {
      const moments = gsap.utils.toArray<HTMLElement>(`.${s.slot}`);
      const turn = rail.current!.querySelector<HTMLElement>("[data-strand-turn]");
      const spin = Number(turn?.dataset.spin ?? 720);

      const timeline = gsap.timeline({
        scrollTrigger: {
          trigger: rail.current,
          start: "top top",
          end: () => `+=${window.innerHeight * (STAGES.length - 0.6)}`,
          pin: sticky.current,
          scrub: 1,
          invalidateOnRefresh: true,
        },
      });

      if (turn) {
        timeline.fromTo(
          turn,
          { rotateY: 0 },
          { rotateY: spin, ease: "none", duration: STAGES.length },
          0,
        );
      }

      // each moment owns one unit of the timeline: rise, hold, leave
      moments.forEach((moment, i) => {
        timeline
          .fromTo(
            moment,
            { autoAlpha: 0, y: 46 },
            { autoAlpha: 1, y: 0, duration: 0.28, ease: "power2.out" },
            i,
          )
          .to(moment, { autoAlpha: 0, y: -46, duration: 0.28, ease: "power2.in" }, i + 0.72);
      });
    }, rail);

    // webfonts change the header height, so re-measure once they settle
    document.fonts?.ready.then(() => ScrollTrigger.refresh());

    return () => {
      ctx.revert();
      delete section.dataset.enhanced;
    };
  }, []);

  return (
    <section ref={rail} className={s.rail} id="how-it-works">
      <div ref={sticky} className={s.sticky}>
        <div className={s.head}>
          <p className="eyebrow">One conversation, end to end</p>
          <h2 className="h2">Every message follows the same path.</h2>
        </div>

        <div className={s.scene}>
          <Strand rungs={38} radius={112} gap={19} step={19} spin={720} idle={false} />
          <div className={s.slots}>
            {STAGES.map((stage, i) => (
              <div key={stage.title} className={s.slot} data-side={i % 2 === 0 ? "l" : "r"}>
                <i className={s.tick} />
                <h3>{stage.title}</h3>
                <p>{stage.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
