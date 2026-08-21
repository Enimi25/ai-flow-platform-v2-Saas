"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowClockwise, CheckCircle, Info, WarningCircle, XCircle } from "@phosphor-icons/react";
import s from "./activity.module.css";

type Level = "info" | "success" | "warn" | "error";
type Event = { id: string; at: string; kind: string; title: string; detail?: string; level: Level };
type Step = { id: string; label: string; done: boolean };
type Models = { order: string[]; providers: { id: string; configured: boolean; light: string | null; heavy: string | null }[] };

const ICON = { info: Info, success: CheckCircle, warn: WarningCircle, error: XCircle } as const;

export function ActivityClient() {
  const [events, setEvents] = useState<Event[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [progress, setProgress] = useState(0);
  const [models, setModels] = useState<Models | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const response = await fetch("/api/activity");
    if (!response.ok) return setLoading(false);
    const data = await response.json();
    setEvents(data.events);
    setSteps(data.steps);
    setProgress(data.progress);
    setModels(data.models ?? null);
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(load, 15_000);
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <div className={s.wrap}>
      <section className={s.setup}>
        <div className={s.setupHead}>
          <div>
            <h2>Setup</h2>
            <p>What is connected, and what is still waiting.</p>
          </div>
          <b className="num">{progress}%</b>
        </div>
        <div className={s.bar}><i style={{ width: `${progress}%` }} /></div>
        <ul className={s.steps}>
          {steps.map((step) => (
            <li key={step.id} data-done={step.done || undefined}>
              {step.done ? <CheckCircle size={18} weight="fill" /> : <Info size={18} />}
              {step.label}
            </li>
          ))}
        </ul>
      </section>

      {models && (
        <section className={s.brains}>
          <h2>Who answers customers</h2>
          <p className={s.brainsLede}>Tried top to bottom until one replies.</p>
          <ol className={s.chain}>
            {models.providers.map((provider, index) => (
              <li key={provider.id} data-on={provider.configured || undefined}>
                <span className={s.rank}>{index + 1}</span>
                <div>
                  <b>{provider.id}</b>
                  <small>{provider.configured ? provider.heavy ?? "ready" : "not configured"}</small>
                </div>
                <span className={provider.configured ? s.up : s.down}>
                  {provider.configured ? "ready" : "off"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className={s.feed}>
        <div className={s.feedHead}>
          <h2>Activity</h2>
          <button type="button" onClick={load} aria-label="Refresh">
            <ArrowClockwise size={16} weight="bold" />
          </button>
        </div>

        {loading ? (
          <ul className={s.skeleton}>
            {[0, 1, 2, 3].map((row) => <li key={row} />)}
          </ul>
        ) : events.length === 0 ? (
          <div className={s.empty}>
            <p>Nothing has happened yet. Sign in, connect a channel, or queue a post and it shows up here the moment it runs.</p>
          </div>
        ) : (
          <ol className={s.log}>
            {events.map((event) => {
              const Icon = ICON[event.level];
              return (
                <li key={event.id} data-level={event.level}>
                  <time className="num" dateTime={event.at}>
                    {new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </time>
                  <Icon size={17} weight="fill" />
                  <div>
                    <b>{event.title}</b>
                    {event.detail && <span>{event.detail}</span>}
                  </div>
                  <code>{event.kind}</code>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}
