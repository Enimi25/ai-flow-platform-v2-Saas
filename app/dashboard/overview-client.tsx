"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle, Circle } from "@phosphor-icons/react";
import s from "./overview.module.css";

type Lead = { id: string; name: string; email: string; phone: string; source: string; createdAt: string };
type Booking = { id: string; customerName: string; customerEmail: string; service: string; startsAt: string };
type Event = { id: string; title: string; at: string; level: string };
type Step = { id: string; label: string; done: boolean; href: string };

type Data = {
  totals: { leads: number; newLeads: number; queued: number; published: number; upcoming: number };
  recentLeads: Lead[];
  upcoming: Booking[];
  events: Event[];
  steps: Step[];
  progress: number;
};

export function OverviewClient() {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/overview");
      if (response.ok) setData(await response.json());
    })();
  }, []);

  if (!data) return <p className={s.muted}>Loading…</p>;

  const tiles = [
    { label: "Leads", value: data.totals.leads, href: "/leads" },
    { label: "New and unhandled", value: data.totals.newLeads, href: "/leads" },
    { label: "Posts queued", value: data.totals.queued, href: "/content" },
    { label: "Appointments ahead", value: data.totals.upcoming, href: "/calendar" },
  ];

  return (
    <div className={s.wrap}>
      <section className={s.setup}>
        <div className={s.setupHead}>
          <div>
            <h2>Setup</h2>
            <p>Each step switches on by itself the moment it is done.</p>
          </div>
          <b className="num">{data.progress}%</b>
        </div>
        <div className={s.bar}><i style={{ width: `${data.progress}%` }} /></div>
        <ul className={s.steps}>
          {data.steps.map((step) => (
            <li key={step.id} data-done={step.done || undefined}>
              {step.done ? <CheckCircle size={18} weight="fill" /> : <Circle size={18} />}
              <Link href={step.href}>{step.label}</Link>
            </li>
          ))}
        </ul>
      </section>

      <div className={s.tiles}>
        {tiles.map((tile) => (
          <Link key={tile.label} href={tile.href} className={s.tile}>
            <span>{tile.label}</span>
            <b className="num">{tile.value}</b>
          </Link>
        ))}
      </div>

      <div className={s.pair}>
        <section className={s.panel}>
          <div className={s.panelHead}>
            <h2>Latest leads</h2>
            <Link href="/leads">All <ArrowRight size={13} weight="bold" /></Link>
          </div>
          {data.recentLeads.length === 0 ? (
            <p className={s.muted}>No leads yet. The first one appears here on its own.</p>
          ) : (
            <ul className={s.rows}>
              {data.recentLeads.map((lead) => (
                <li key={lead.id}>
                  <div>
                    <b>{lead.name || lead.email || lead.phone}</b>
                    <span>{lead.source}</span>
                  </div>
                  <time className="num" dateTime={lead.createdAt}>
                    {new Date(lead.createdAt).toLocaleDateString()}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={s.panel}>
          <div className={s.panelHead}>
            <h2>What happened</h2>
            <Link href="/activity">All <ArrowRight size={13} weight="bold" /></Link>
          </div>
          {data.events.length === 0 ? (
            <p className={s.muted}>Nothing has run yet.</p>
          ) : (
            <ul className={s.rows}>
              {data.events.map((event) => (
                <li key={event.id} data-level={event.level}>
                  <div><b>{event.title}</b></div>
                  <time className="num" dateTime={event.at}>
                    {new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
