"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowClockwise, EnvelopeSimple, Phone } from "@phosphor-icons/react";
import s from "./leads.module.css";

type Lead = {
  id: string;
  name: string;
  email: string;
  phone: string;
  source: string;
  message: string;
  status: "new" | "in_progress" | "converted" | "lost";
  createdAt: string;
};

const STATUSES: Lead["status"][] = ["new", "in_progress", "converted", "lost"];
const LABEL: Record<Lead["status"], string> = {
  new: "New",
  in_progress: "In progress",
  converted: "Converted",
  lost: "Lost",
};

export function LeadsClient({ canEdit }: { canEdit: boolean }) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<"all" | Lead["status"]>("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const response = await fetch("/api/leads");
    if (!response.ok) return setLoading(false);
    const data = await response.json();
    setLeads(data.leads);
    setCounts(data.counts);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => window.clearInterval(timer);
  }, [load]);

  async function move(id: string, status: Lead["status"]) {
    setLeads((current) => current.map((lead) => (lead.id === id ? { ...lead, status } : lead)));
    await fetch("/api/leads", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, status }),
    });
    void load();
  }

  const shown = filter === "all" ? leads : leads.filter((lead) => lead.status === filter);

  return (
    <div className={s.wrap}>
      <div className={s.bar}>
        <div className={s.filters}>
          <button type="button" data-on={filter === "all" || undefined} onClick={() => setFilter("all")}>
            All <span className="num">{leads.length}</span>
          </button>
          {STATUSES.map((status) => (
            <button key={status} type="button" data-on={filter === status || undefined} onClick={() => setFilter(status)}>
              {LABEL[status]} <span className="num">{counts[status] ?? 0}</span>
            </button>
          ))}
        </div>
        <button type="button" className={s.refresh} onClick={load} aria-label="Refresh">
          <ArrowClockwise size={16} weight="bold" />
        </button>
      </div>

      {loading ? (
        <p className={s.muted}>Loading…</p>
      ) : shown.length === 0 ? (
        <div className={s.empty}>
          <p>
            No leads here yet. The moment a visitor leaves an email or a phone number in the chat,
            it lands on this screen by itself.
          </p>
        </div>
      ) : (
        <ul className={s.list}>
          {shown.map((lead) => (
            <li key={lead.id} data-status={lead.status}>
              <div className={s.who}>
                <b>{lead.name || lead.email || lead.phone}</b>
                <div className={s.contacts}>
                  {lead.email && (
                    <a href={`mailto:${lead.email}`}><EnvelopeSimple size={15} /> {lead.email}</a>
                  )}
                  {lead.phone && (
                    <a href={`tel:${lead.phone.replace(/\s/g, "")}`}><Phone size={15} /> {lead.phone}</a>
                  )}
                </div>
                {lead.message && <p className={s.message}>{lead.message}</p>}
              </div>

              <div className={s.meta}>
                <span className={s.source}>{lead.source}</span>
                <time className="num" dateTime={lead.createdAt}>
                  {new Date(lead.createdAt).toLocaleString()}
                </time>
                <select
                  value={lead.status}
                  onChange={(event) => move(lead.id, event.target.value as Lead["status"])}
                  disabled={!canEdit}
                  aria-label="Lead status"
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>{LABEL[status]}</option>
                  ))}
                </select>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
