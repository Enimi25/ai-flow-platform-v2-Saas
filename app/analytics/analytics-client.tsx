"use client";

import { useEffect, useState } from "react";
import s from "./analytics.module.css";

type Data = {
  totals: {
    leads: number; converted: number; conversionRate: number;
    published: number; queued: number; bookings: number;
    revenueCents: number; currency: string;
  };
  leadsByStatus: Record<string, number>;
  leadsBySource: Record<string, number>;
  daily: { day: string; count: number }[];
};

function Bars({ data }: { data: { day: string; count: number }[] }) {
  const peak = Math.max(1, ...data.map((point) => point.count));
  return (
    <div className={s.chart} role="img" aria-label="Leads per day over the last two weeks">
      {data.map((point) => (
        <div key={point.day} className={s.col} title={`${point.day}: ${point.count}`}>
          <i style={{ height: `${(point.count / peak) * 100}%` }} data-empty={point.count === 0 || undefined} />
          <small>{point.day.slice(8)}</small>
        </div>
      ))}
    </div>
  );
}

function Split({ title, rows }: { title: string; rows: Record<string, number> }) {
  const total = Object.values(rows).reduce((sum, value) => sum + value, 0);
  const entries = Object.entries(rows);
  return (
    <section className={s.panel}>
      <h2>{title}</h2>
      {entries.length === 0 ? (
        <p className={s.muted}>Nothing yet.</p>
      ) : (
        <ul className={s.rows}>
          {entries.map(([key, value]) => (
            <li key={key}>
              <span>{key.replace(/_/g, " ")}</span>
              <b className="num">{value}</b>
              <i style={{ width: `${total ? (value / total) * 100 : 0}%` }} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function AnalyticsClient() {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/analytics");
      if (response.ok) setData(await response.json());
    })();
  }, []);

  if (!data) return <p className={s.muted}>Loading…</p>;

  const { totals } = data;
  const tiles = [
    { label: "Leads", value: totals.leads },
    { label: "Converted", value: totals.converted },
    { label: "Conversion", value: `${totals.conversionRate}%` },
    { label: "Booked and paid", value: totals.bookings },
    { label: "Revenue", value: `${(totals.revenueCents / 100).toFixed(2)} ${totals.currency}` },
    { label: "Posts published", value: totals.published },
    { label: "Posts queued", value: totals.queued },
  ];

  return (
    <div className={s.wrap}>
      <div className={s.tiles}>
        {tiles.map((tile) => (
          <div key={tile.label} className={s.tile}>
            <span>{tile.label}</span>
            <b className="num">{tile.value}</b>
          </div>
        ))}
      </div>

      <section className={s.panel}>
        <h2>Leads per day</h2>
        <Bars data={data.daily} />
      </section>

      <div className={s.pair}>
        <Split title="By status" rows={data.leadsByStatus} />
        <Split title="By source" rows={data.leadsBySource} />
      </div>
    </div>
  );
}
