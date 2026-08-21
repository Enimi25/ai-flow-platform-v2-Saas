"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CalendarPlus, Check, Clock, GoogleLogo, LinkSimple, Warning } from "@phosphor-icons/react";
import styles from "./calendar.module.css";

type DayItem = { iso: string; weekday: string; day: string; month: string };

function makeDays(today: string, offset = 0): DayItem[] {
  const base = new Date(`${today}T12:00:00Z`);
  base.setUTCDate(base.getUTCDate() + offset);
  return Array.from({ length: 9 }, (_, index) => {
    const date = new Date(base);
    date.setUTCDate(base.getUTCDate() + index - 2);
    return {
      iso: date.toISOString().slice(0, 10),
      weekday: new Intl.DateTimeFormat("en", { weekday: "short", timeZone: "UTC" }).format(date),
      day: String(date.getUTCDate()),
      month: new Intl.DateTimeFormat("en", { month: "short", timeZone: "UTC" }).format(date),
    };
  });
}

const previewEvents = [
  { time: "09:30", duration: "30 min", title: "Website demo request", contact: "Example lead", source: "Website" },
  { time: "11:00", duration: "45 min", title: "Service consultation", contact: "Example lead", source: "Facebook" },
  { time: "14:30", duration: "30 min", title: "Follow-up call", contact: "Example lead", source: "Instagram" },
];

export function CalendarWorkspace({ authenticated, setupRequired, today }: { authenticated: boolean; setupRequired: boolean; today: string }) {
  const [offset, setOffset] = useState(0);
  const days = useMemo(() => makeDays(today, offset), [today, offset]);
  const [selected, setSelected] = useState(today);
  const selectedDay = days.find((day) => day.iso === selected) || days[2];

  function shiftDates(change: number) {
    const nextOffset = offset + change;
    const nextDays = makeDays(today, nextOffset);
    setOffset(nextOffset);
    setSelected(nextDays[2].iso);
  }

  return (
    <div className={styles.page}>
      <header className={styles.heading}>
        <div><h1>Calendar</h1><p>Review AI-booked appointments and protect the hours your team needs.</p></div>
        <div className={styles.actions}>
          <button className={styles.secondary} disabled title="Connect a calendar to create appointments"><CalendarPlus />New appointment</button>
          {authenticated ? <a className={styles.primary} href="/api/calendar/connect"><GoogleLogo weight="bold" />Connect Google Calendar</a> : <Link className={styles.primary} href="/login?returnTo=/calendar&reason=session">Sign in to connect</Link>}
        </div>
      </header>

      {setupRequired && <div className={styles.notice}><Warning weight="fill" /><div><b>Google Calendar setup is incomplete</b><p>Add the OAuth URL and Google credentials in the server environment, then connect again.</p></div></div>}

      <section className={styles.dateRail} aria-label="Choose date">
        <button aria-label="Previous dates" onClick={() => shiftDates(-7)}><ArrowLeft /></button>
        {days.map((item) => <button key={item.iso} className={selected === item.iso ? styles.current : undefined} onClick={() => setSelected(item.iso)} aria-pressed={selected === item.iso}><span>{item.weekday}</span><strong>{item.day}</strong><small>{item.month}</small></button>)}
        <button aria-label="Next dates" onClick={() => shiftDates(7)}><ArrowRight /></button>
      </section>

      <div className={styles.layout}>
        <section className={styles.agenda}>
          <div className={styles.agendaHeader}><div><h2>{selectedDay.weekday}, {selectedDay.month} {selectedDay.day}</h2><p>Example schedule until a calendar is connected</p></div><span>Preview data</span></div>
          <div className={styles.timeline}>
            {previewEvents.map((event) => <article key={`${event.time}-${event.title}`}><time>{event.time}</time><div className={styles.event}><div><h3>{event.title}</h3><p>{event.contact} <span>{event.source}</span></p></div><small>{event.duration}</small></div></article>)}
            <article className={styles.openSlot}><time>16:00</time><div><Clock /><span>Available for booking</span></div></article>
          </div>
        </section>

        <aside className={styles.side}>
          <section className={styles.connection}><div className={styles.sideTitle}><GoogleLogo weight="bold" /><div><h2>Google Calendar</h2><p>Not connected</p></div></div><p>Connect a calendar to prevent double booking and sync AI-created appointments.</p>{authenticated ? <a href="/api/calendar/connect"><LinkSimple />Connect calendar</a> : <Link href="/login?returnTo=/calendar&reason=session"><LinkSimple />Sign in to connect</Link>}</section>
          <section className={styles.availability}><div className={styles.sideTitle}><Clock /><div><h2>Booking hours</h2><p>Default availability</p></div></div><dl><div><dt>Monday - Friday</dt><dd>09:00 - 17:00</dd></div><div><dt>Saturday</dt><dd>10:00 - 14:00</dd></div><div><dt>Sunday</dt><dd>Unavailable</dd></div></dl><button disabled title="Connect a calendar to edit availability">Edit availability</button></section>
          <section className={styles.ready}><Check weight="bold" /><p>AI FLOW checks availability before offering a time to a customer.</p></section>
        </aside>
      </div>
    </div>
  );
}
