"use client";

import { useEffect, useState } from "react";
import { ChatCircleDots, UserCircle, Sparkle } from "@phosphor-icons/react";
import s from "./conversations.module.css";

type Turn = { role: "customer" | "agent"; text: string; at: string };
type Thread = { id: string; visitorId: string; source: string; turns: Turn[]; startedAt: string; lastAt: string; leadId?: string };

export function ConversationsClient() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [withLead, setWithLead] = useState(0);

  useEffect(() => {
    const load = async () => {
      const response = await fetch("/api/conversations");
      if (response.ok) {
        const data = await response.json();
        setThreads(data.threads);
        setWithLead(data.withLead);
        setOpen((current) => current ?? data.threads[0]?.id ?? null);
      }
      setLoading(false);
    };
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => window.clearInterval(timer);
  }, []);

  if (loading) return <p className={s.muted}>Loading…</p>;

  if (threads.length === 0) {
    return (
      <div className={s.empty}>
        <ChatCircleDots size={30} weight="fill" />
        <p>
          No conversations yet. Every exchange the widget has with a visitor is kept here,
          so you can read what customers actually ask.
        </p>
      </div>
    );
  }

  const current = threads.find((thread) => thread.id === open) ?? threads[0];

  return (
    <div className={s.wrap}>
      <div className={s.summary}>
        <span><b className="num">{threads.length}</b> conversations</span>
        <span><b className="num">{withLead}</b> left contact details</span>
      </div>

      <div className={s.board}>
        <ul className={s.threads}>
          {threads.map((thread) => {
            const last = thread.turns[thread.turns.length - 1];
            return (
              <li key={thread.id}>
                <button type="button" data-on={thread.id === current.id || undefined} onClick={() => setOpen(thread.id)}>
                  <div className={s.threadHead}>
                    <b>{thread.visitorId === "anonymous" ? "Anonymous visitor" : thread.visitorId.slice(0, 14)}</b>
                    {thread.leadId && <span className={s.lead}><Sparkle size={11} weight="fill" /> lead</span>}
                  </div>
                  <p>{last?.text.slice(0, 70) ?? ""}</p>
                  <time className="num" dateTime={thread.lastAt}>{new Date(thread.lastAt).toLocaleString()}</time>
                </button>
              </li>
            );
          })}
        </ul>

        <section className={s.thread}>
          <header>
            <UserCircle size={22} weight="fill" />
            <div>
              <b>{current.visitorId === "anonymous" ? "Anonymous visitor" : current.visitorId}</b>
              <span>{current.source} · started {new Date(current.startedAt).toLocaleString()}</span>
            </div>
          </header>
          <div className={s.log}>
            {current.turns.map((turn, index) => (
              <p key={`${turn.at}-${index}`} data-role={turn.role}>{turn.text}</p>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
