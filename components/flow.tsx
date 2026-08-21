"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Strand from "./strand";
import s from "./flow.module.css";

gsap.registerPlugin(ScrollTrigger);

/**
 * One real conversation, carried through all four stages.
 *
 * The section used to be a large animation beside four one-line captions, which
 * read as decoration. Showing the actual messages is what makes the claim
 * legible: the same enquiry moves down the page and arrives as an appointment.
 */
const STAGES = [
  {
    step: "01",
    title: "A customer writes",
    body: "Someone messages your site, Messenger, Instagram or WhatsApp. Any hour, any language.",
    fact: "23:40, Saturday",
    said: { from: "customer", text: "Скольько стоит чистка? Можно в воскресенье?" },
    note: "Typed in Russian, at midnight, with a typo. All three are normal.",
  },
  {
    step: "02",
    title: "The agent answers",
    body: "It replies from what you told it, in the language they used, and never invents a price.",
    fact: "4 seconds later",
    said: { from: "agent", text: "Чистка — 85. В воскресенье мы закрыты, но есть суббота в 10:00 или 11:00." },
    note: "It knew Sunday was shut because your opening hours say so.",
  },
  {
    step: "03",
    title: "The lead is kept",
    body: "Name, phone, channel and the whole conversation are filed before the chat ends.",
    fact: "Saved automatically",
    said: { from: "customer", text: "Анна, +7 916 445 22 10. Давайте субботу в 11." },
    note: "A phone number typed mid-sentence still lands in your leads.",
  },
  {
    step: "04",
    title: "The slot is booked",
    body: "The appointment goes into the calendar, checked against what is already taken.",
    fact: "22.08.2026, 11:00",
    said: { from: "agent", text: "Записала вас на субботу, 11:00. До встречи!" },
    note: "If someone took that slot a second earlier, it says so and offers the next.",
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
                <p className={s.step}>{stage.step}<span>{stage.fact}</span></p>
                <h3>{stage.title}</h3>
                <p className={s.body}>{stage.body}</p>
                <p className={s.said} data-from={stage.said.from}>{stage.said.text}</p>
                <p className={s.note}>{stage.note}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
