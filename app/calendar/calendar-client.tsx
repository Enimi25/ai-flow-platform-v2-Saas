"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarCheck, Clock, WarningCircle, CheckCircle } from "@phosphor-icons/react";
import s from "./calendar.module.css";

type Booking = {
  id: string; customerName: string; customerEmail: string; service: string;
  startsAt: string; endsAt: string; amountCents: number; currency: string;
  calendarLink?: string; error?: string;
};

type Data = {
  upcoming: Booking[]; past: Booking[]; held: Booking[];
  calendar: { connected: boolean; calendarId: string | null; googleReady: boolean };
  paymentsReady: boolean;
};

function when(booking: Booking) {
  const start = new Date(booking.startsAt);
  const end = new Date(booking.endsAt);
  return `${start.toLocaleDateString()} · ${start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} to ${end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export function CalendarClient() {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/bookings");
      if (response.ok) setData(await response.json());
    })();
  }, []);

  if (!data) return <p className={s.muted}>Loading…</p>;

  return (
    <div className={s.wrap}>
      <section className={s.status} data-on={data.calendar.connected || undefined}>
        <CalendarCheck size={26} weight="fill" />
        <div>
          <b>{data.calendar.connected ? "Calendar connected" : "No calendar connected yet"}</b>
          <p>
            {data.calendar.connected
              ? `Paid appointments are written into ${data.calendar.calendarId ?? "your main calendar"}.`
              : data.calendar.googleReady
                ? "Sign in with Google once and pick the calendar bookings should land in."
                : "Google sign in is not configured on this server yet."}
          </p>
        </div>
        {!data.calendar.connected && data.calendar.googleReady && (
          <Link className="btn btn-sm" href="/api/auth/google?next=/calendar/confirm">Connect</Link>
        )}
      </section>

      {false && (
        <p className={s.warn}>
          <WarningCircle size={18} weight="fill" />
          Payments are not connected, so a customer cannot finish a booking yet.
        </p>
      )}

      {data.held.length > 0 && (
        <section className={s.panel}>
          <h2>Waiting for payment</h2>
          <ul className={s.list}>
            {data.held.map((booking) => (
              <li key={booking.id} data-held>
                <div>
                  <b>{booking.service}</b>
                  <span>{booking.customerEmail}</span>
                </div>
                <time className="num">{when(booking)}</time>
                <span className={s.tag}><Clock size={13} weight="fill" /> Held</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={s.panel}>
        <h2>Upcoming</h2>
        {data.upcoming.length === 0 ? (
          <p className={s.muted}>
            Nothing booked yet. When the agent agrees a time with a customer, it lands here straight away.
          </p>
        ) : (
          <ul className={s.list}>
            {data.upcoming.map((booking) => (
              <li key={booking.id}>
                <div>
                  <b>{booking.service}</b>
                  <span>{booking.customerName || booking.customerEmail}</span>
                </div>
                <time className="num">{when(booking)}</time>
                <span className={s.paid}>
                  <CheckCircle size={13} weight="fill" />
                  {(booking.amountCents / 100).toFixed(2)} {booking.currency.toUpperCase()}
                </span>
                {booking.calendarLink && (
                  <a href={booking.calendarLink} target="_blank" rel="noreferrer" className={s.link}>Open</a>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.past.length > 0 && (
        <section className={s.panel}>
          <h2>Done</h2>
          <ul className={s.list}>
            {data.past.map((booking) => (
              <li key={booking.id} data-past>
                <div><b>{booking.service}</b><span>{booking.customerEmail}</span></div>
                <time className="num">{when(booking)}</time>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
