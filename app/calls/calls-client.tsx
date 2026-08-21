"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowClockwise, Check, Phone, PlusCircle, Sparkle, Warning } from "@phosphor-icons/react";
import { OUTCOMES, OUTCOME_LABEL, type Call, type Outcome } from "@/lib/calls/types";
import s from "./calls.module.css";

type Queueable = { id: string; name: string; phone: string; source: string; message: string; createdAt: string };
type Need = { name: string; done: boolean; note: string };
type Payload = {
  calls: Call[];
  stats: { waiting: number; called: number; reached: number; booked: number; conversion: number };
  queueable: Queueable[];
  telephony: { ready: boolean; provider: string | null; missing: string[]; needs: Need[] };
};

export function CallsClient({ signedIn }: { signedIn: boolean }) {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/calls", { cache: "no-store" });
    if (response.ok) setData((await response.json()) as Payload);
  }, []);

  useEffect(() => {
    if (signedIn) void load();
  }, [signedIn, load]);

  if (!signedIn) {
    return <p className={s.empty}>Sign in to see who is waiting for a call.</p>;
  }
  if (!data) return <p className={s.empty}>Loading…</p>;

  async function queue(lead: Queueable) {
    setBusy(lead.id);
    await fetch("/api/calls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        leadId: lead.id,
        name: lead.name,
        phone: lead.phone,
        reason: `Wrote on ${lead.source} and left a number.`,
        context: lead.message,
      }),
    });
    await load();
    setBusy(null);
  }

  async function brief(call: Call) {
    setBusy(call.id);
    await fetch("/api/calls", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: call.id, action: "script" }),
    });
    await load();
    setBusy(null);
  }

  async function record(call: Call, outcome: Outcome) {
    setBusy(call.id);
    const dueAt =
      outcome === "callback" ? new Date(Date.now() + 24 * 3600_000).toISOString() : undefined;
    await fetch("/api/calls", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: call.id, action: "outcome", outcome, notes, dueAt }),
    });
    setNotes("");
    setOpen(null);
    await load();
    setBusy(null);
  }

  const waiting = data.calls.filter((call) => call.status !== "done");
  const done = data.calls.filter((call) => call.status === "done");

  return (
    <div className={s.page}>
      <section className={s.stats}>
        {[
          ["Waiting", data.stats.waiting],
          ["Called", data.stats.called],
          ["Reached", data.stats.reached],
          ["Booked", data.stats.booked],
          ["Of those reached", `${data.stats.conversion}%`],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <b className="num">{value}</b>
            <span>{label}</span>
          </div>
        ))}
      </section>

      {!data.telephony.ready && (
        <section className={`panel ${s.notice}`}>
          <div className={s.noticeHead}>
            <Warning weight="fill" />
            <div>
              <b>The agent does not place calls yet</b>
              <p>
                No provider is connected, so nothing here dials out. Everything else works: the
                queue, the brief and the outcome are useful the moment somebody picks up a handset.
              </p>
            </div>
          </div>
          <ul className={s.needs}>
            {data.telephony.needs.map((need) => (
              <li key={need.name} data-done={need.done}>
                {need.done ? <Check weight="bold" /> : <span className={s.dot} />}
                <div>
                  <b>{need.name}</b>
                  <small>{need.note}</small>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className={s.board}>
        <section>
          <h2 className={s.sectionTitle}>To call <span>{waiting.length}</span></h2>

          {!waiting.length && <p className={s.empty}>Nobody is waiting. Add someone from the right.</p>}

          {waiting.map((call) => (
            <article key={call.id} className={`panel ${s.call}`}>
              <header>
                <div>
                  <b>{call.name || "No name given"}</b>
                  <a href={`tel:${call.phone.replace(/\s/g, "")}`} className={s.phone}>
                    <Phone weight="fill" /> {call.phone}
                  </a>
                </div>
                {call.attempts > 0 && <span className={s.attempts}>{call.attempts} tried</span>}
              </header>

              <p className={s.reason}>{call.reason}</p>
              {call.context && <p className={s.context}>&ldquo;{call.context}&rdquo;</p>}

              {call.script ? (
                <div className={s.script}>
                  <p className={s.scriptLabel}>Open with</p>
                  <p className={s.opening}>{call.script.opening}</p>

                  {!!call.script.points.length && (
                    <>
                      <p className={s.scriptLabel}>Cover</p>
                      <ul>{call.script.points.map((point) => <li key={point}>{point}</li>)}</ul>
                    </>
                  )}

                  {!!call.script.objections.length && (
                    <>
                      <p className={s.scriptLabel}>If they say</p>
                      <dl>
                        {call.script.objections.map((item) => (
                          <div key={item.heard}>
                            <dt>{item.heard}</dt>
                            <dd>{item.answer}</dd>
                          </div>
                        ))}
                      </dl>
                    </>
                  )}

                  <p className={s.scriptLabel}>Ask for the appointment</p>
                  <p className={s.opening}>{call.script.closing}</p>
                </div>
              ) : (
                <button
                  type="button"
                  className={s.ghost}
                  disabled={busy === call.id}
                  onClick={() => brief(call)}
                >
                  <Sparkle weight="fill" />
                  {busy === call.id ? "Writing the brief…" : "Write me a brief for this person"}
                </button>
              )}

              {open === call.id ? (
                <div className={s.outcome}>
                  <textarea
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="What was said?"
                    rows={2}
                  />
                  <div className={s.outcomeRow}>
                    {OUTCOMES.map((outcome) => (
                      <button
                        key={outcome}
                        type="button"
                        data-kind={outcome}
                        disabled={busy === call.id}
                        onClick={() => record(call, outcome)}
                      >
                        {OUTCOME_LABEL[outcome]}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <button type="button" className={s.primary} onClick={() => setOpen(call.id)}>
                  Log how it went
                </button>
              )}
            </article>
          ))}
        </section>

        <aside>
          <h2 className={s.sectionTitle}>
            Left a number <span>{data.queueable.length}</span>
            <button type="button" className={s.refresh} onClick={() => load()} aria-label="Refresh">
              <ArrowClockwise weight="bold" />
            </button>
          </h2>

          {!data.queueable.length && <p className={s.empty}>Everyone with a number is already in the queue.</p>}

          {data.queueable.map((lead) => (
            <div key={lead.id} className={`panel ${s.lead}`}>
              <b>{lead.name || lead.phone}</b>
              <small>{lead.source} · {lead.phone}</small>
              {lead.message && <p>{lead.message}</p>}
              <button type="button" disabled={busy === lead.id} onClick={() => queue(lead)}>
                <PlusCircle weight="fill" /> {busy === lead.id ? "Adding…" : "Add to the queue"}
              </button>
            </div>
          ))}

          {!!done.length && (
            <>
              <h2 className={s.sectionTitle}>Done <span>{done.length}</span></h2>
              {done.slice(0, 10).map((call) => (
                <div key={call.id} className={`panel ${s.doneRow}`}>
                  <b>{call.name || call.phone}</b>
                  <span data-kind={call.outcome}>{call.outcome ? OUTCOME_LABEL[call.outcome] : ""}</span>
                  {call.notes && <p>{call.notes}</p>}
                </div>
              ))}
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
