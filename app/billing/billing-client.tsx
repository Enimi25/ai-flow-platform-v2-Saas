"use client";

import { useEffect, useState } from "react";
import { Check, WarningCircle } from "@phosphor-icons/react";
import s from "./billing.module.css";

type Plan = {
  id: string; name: string; priceCents: number | null; blurb: string;
  includes: string[]; limits: { conversations: number | null; posts: number | null }; featured?: boolean;
};

type Data = {
  plans: Plan[];
  current: string | null;
  paymentsReady: boolean;
  usage: { month: string; conversations: number; leads: number; postsPublished: number; bookingsPaid: number };
};

export function BillingClient() {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/billing");
      if (response.ok) setData(await response.json());
    })();
  }, []);

  if (!data) return <p className={s.muted}>Loading…</p>;

  const usage = [
    { label: "Conversations", value: data.usage.conversations },
    { label: "Leads captured", value: data.usage.leads },
    { label: "Posts published", value: data.usage.postsPublished },
    { label: "Paid bookings", value: data.usage.bookingsPaid },
  ];

  return (
    <div className={s.wrap}>
      <section className={s.usage}>
        <div className={s.usageHead}>
          <h2>This month</h2>
          <span className="num">{data.usage.month}</span>
        </div>
        <div className={s.tiles}>
          {usage.map((entry) => (
            <div key={entry.label}>
              <span>{entry.label}</span>
              <b className="num">{entry.value}</b>
            </div>
          ))}
        </div>
      </section>

      {!data.paymentsReady && (
        <p className={s.warn}>
          <WarningCircle size={18} weight="fill" />
          Payments are not connected on this server, so no plan can be bought yet.
        </p>
      )}

      <div className={s.plans}>
        {data.plans.map((plan) => (
          <section key={plan.id} className={plan.featured ? `${s.plan} ${s.featured}` : s.plan}>
            <h3>{plan.name}</h3>
            <p className={s.blurb}>{plan.blurb}</p>
            <p className={`num ${s.price}`}>
              {plan.priceCents === null ? "Custom" : `$${(plan.priceCents / 100).toFixed(0)}`}
              {plan.priceCents !== null && <span>/month</span>}
            </p>
            <ul>
              {plan.includes.map((line) => (
                <li key={line}><Check size={15} weight="bold" /> {line}</li>
              ))}
            </ul>
            <button
              type="button"
              className={plan.featured ? "btn" : "btn btn-ghost"}
              disabled={!data.paymentsReady}
            >
              {data.current === plan.id ? "Current plan" : data.paymentsReady ? "Choose" : "Payments off"}
            </button>
          </section>
        ))}
      </div>
    </div>
  );
}
