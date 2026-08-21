"use client";

import { useState } from "react";
import {
  CalendarCheck,
  ChatCircleDots,
  Check,
  Lightning,
  Minus,
  UserList,
} from "@phosphor-icons/react";
import Strand from "./strand";
import s from "./flow.module.css";

/**
 * How it works, as something you can open rather than something you scroll past.
 *
 * This was a pinned scroll animation that revealed one caption at a time beside
 * a large helix. On any given screen it read as empty: a lot of motion, four
 * short lines, and no way to ask it anything. Everything is on the page now, and
 * the stage you tap opens.
 */

const STAGES = [
  {
    key: "writes",
    step: "01",
    icon: ChatCircleDots,
    title: "A customer writes",
    fact: "23:40, Saturday",
    lead: "We hold the channels, so somebody is always there.",
    said: { from: "customer", text: "Скольько стоит чистка? Можно в воскресенье?" },
    detail: [
      "Your website, Facebook Messenger, Instagram and WhatsApp all arrive in one place.",
      "Any hour, including the ones you are asleep for. Half of all enquiries land outside working hours and most of those never get answered at all.",
      "Any language, and Russian typed in Latin letters counts as Russian. Typos too.",
    ],
    proof: "You connect an account once. After that nobody on your side touches it.",
  },
  {
    key: "answers",
    step: "02",
    icon: Lightning,
    title: "The agent answers",
    fact: "4 seconds later",
    lead: "From what you told it, in the language they used.",
    said: { from: "agent", text: "Чистка — 85. В воскресенье мы закрыты, но есть суббота в 10:00 или 11:00." },
    detail: [
      "It knows your prices, your address, your hours and what you do not do, because you wrote that once in plain language.",
      "It knew Sunday was shut without being told twice: the answer comes from your real opening hours, not from a guess.",
      "When it does not know, it says so and asks how to reach you. It will not invent a price to keep the conversation going.",
    ],
    proof: "Ask it something it was never told. It refuses instead of guessing. That is the whole difference.",
  },
  {
    key: "lead",
    step: "03",
    icon: UserList,
    title: "The lead is kept",
    fact: "Before the chat ends",
    lead: "Nothing depends on anyone remembering to write it down.",
    said: { from: "customer", text: "Анна, +7 916 445 22 10. Давайте субботу в 11." },
    detail: [
      "Name, phone, email, which channel they came from and the entire conversation.",
      "A phone number typed in the middle of a sentence still lands in your leads. So does one given three messages earlier.",
      "Every workspace sees only its own. Nobody without your sign-in can read a single contact.",
    ],
    proof: "Open Leads tomorrow morning and last night's enquiries are already sitting there.",
  },
  {
    key: "booked",
    step: "04",
    icon: CalendarCheck,
    title: "The slot is booked",
    fact: "22.08.2026, 11:00",
    lead: "A real appointment, not a promise to call back.",
    said: { from: "agent", text: "Записала вас на субботу, 11:00. До встречи!" },
    detail: [
      "Only times that are genuinely free are ever offered, worked out from your hours and what is already taken.",
      "The slot is checked again at the moment of booking. If somebody took it a second earlier, the customer hears that and gets the next one.",
      "The confirmation carries the exact date and time, so a misunderstanding is visible instead of turning up a day late.",
    ],
    proof: "It books from a direct message too. An Instagram customer is not a lesser customer.",
  },
] as const;

const COMPARISON = [
  {
    what: "Answers a question it was not scripted for",
    us: true,
    bot: false,
    hire: true,
    note: "A button menu can only offer what somebody thought of in advance.",
  },
  {
    what: "Replies at 3am on a Sunday",
    us: true,
    bot: true,
    hire: false,
    note: "This is where most of the lost enquiries are.",
  },
  {
    what: "Refuses to invent a price",
    us: true,
    bot: true,
    hire: true,
    note: "Most AI assistants will happily make one up. Ours answers that it does not know.",
  },
  {
    what: "Books against your real calendar",
    us: true,
    bot: false,
    hire: true,
    note: "Not a request form. The appointment exists when the chat ends.",
  },
  {
    what: "Writes and publishes your social posts",
    us: true,
    bot: false,
    hire: true,
    note: "From your own description, on a schedule, without being asked.",
  },
  {
    what: "Costs less than one day of wages a month",
    us: true,
    bot: true,
    hire: false,
    note: "$39 to start.",
  },
] as const;

export default function Flow() {
  const [open, setOpen] = useState<string>(STAGES[0].key);
  const active = STAGES.find((stage) => stage.key === open) ?? STAGES[0];

  return (
    <section className={s.rail} id="how-it-works">
      <div className={s.head}>
        <p className="eyebrow">One conversation, end to end</p>
        <h2 className="h2">Every message follows the same path.</h2>
        <p className={s.strap}>
          We run your social channels for you. Whoever writes, whenever they write, the agent
          answers and books them in. <b>Not one missed customer, 24/7, 365 days a year.</b>
        </p>
      </div>

      <div className={s.board}>
        <div className={s.steps} role="tablist" aria-label="How it works">
          {STAGES.map((stage) => {
            const Icon = stage.icon;
            const isOpen = stage.key === open;
            return (
              <button
                key={stage.key}
                type="button"
                role="tab"
                aria-selected={isOpen}
                className={s.step}
                data-open={isOpen}
                onClick={() => setOpen(stage.key)}
              >
                <span className={s.stepIcon}><Icon weight="fill" /></span>
                <span className={s.stepText}>
                  <em>{stage.step}</em>
                  <b>{stage.title}</b>
                  <small>{stage.lead}</small>
                </span>
                <span className={s.stepFact}>{stage.fact}</span>
              </button>
            );
          })}
        </div>

        <div className={s.detail} role="tabpanel" aria-label={active.title}>
          <p className={s.said} data-from={active.said.from}>{active.said.text}</p>

          <ul className={s.points}>
            {active.detail.map((line) => (
              <li key={line}><Check weight="bold" />{line}</li>
            ))}
          </ul>

          <p className={s.proof}>{active.proof}</p>

          <div className={s.helix} aria-hidden="true">
            <Strand rungs={26} radius={78} gap={17} step={17} spin={360} />
          </div>
        </div>
      </div>

      <div className={s.compare}>
        <h3 className={s.compareTitle}>Why this rather than the alternatives</h3>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th scope="col">What you actually need</th>
                <th scope="col">AI FLOW</th>
                <th scope="col">A chatbot with buttons</th>
                <th scope="col">Hiring someone</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row) => (
                <tr key={row.what}>
                  <th scope="row">
                    {row.what}
                    <small>{row.note}</small>
                  </th>
                  {[row.us, row.bot, row.hire].map((yes, index) => (
                    <td key={index} data-yes={yes} data-us={index === 0}>
                      {yes ? <Check weight="bold" /> : <Minus weight="bold" />}
                      <span className="sr-only">{yes ? "yes" : "no"}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
