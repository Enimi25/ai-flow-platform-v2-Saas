"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarCheck, CheckCircle } from "@phosphor-icons/react";
import s from "./confirm.module.css";

type Calendar = { id: string; summary: string; primary?: boolean };

export function ConfirmClient() {
  const router = useRouter();
  const [calendars, setCalendars] = useState<Calendar[]>([]);
  const [picked, setPicked] = useState<string>("");
  const [state, setState] = useState<"loading" | "ready" | "saving" | "error">("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/google/calendars");
      const data = await response.json();
      if (!response.ok) {
        setError(data.error ?? "Could not read your calendars.");
        setState("error");
        return;
      }
      setCalendars(data.calendars);
      setPicked(data.chosen ?? data.calendars.find((c: Calendar) => c.primary)?.id ?? data.calendars[0]?.id ?? "");
      setState("ready");
    })();
  }, []);

  async function confirm() {
    setState("saving");
    const response = await fetch("/api/google/calendars", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ calendarId: picked }),
    });
    if (!response.ok) {
      const data = await response.json();
      setError(data.error ?? "Could not save that.");
      setState("error");
      return;
    }
    router.push("/calendar?connected=1");
  }

  if (state === "loading") return <p className={s.muted}>Reading your calendars…</p>;

  if (state === "error") {
    return (
      <div className={s.card}>
        <p className={s.error}>{error}</p>
        <a className="btn btn-ghost" href="/api/auth/google?next=/calendar/confirm">Try connecting again</a>
      </div>
    );
  }

  return (
    <div className={s.card}>
      <CalendarCheck size={34} weight="fill" className={s.icon} />
      <h2>Which calendar takes the bookings?</h2>
      <p className={s.muted}>
        Confirmed appointments are written straight into it. You can change this later in settings.
      </p>

      <ul className={s.list}>
        {calendars.map((calendar) => (
          <li key={calendar.id}>
            <button
              type="button"
              onClick={() => setPicked(calendar.id)}
              aria-pressed={picked === calendar.id}
              data-on={picked === calendar.id || undefined}
            >
              <span>
                <b>{calendar.summary}</b>
                {calendar.primary && <small>Main calendar</small>}
              </span>
              {picked === calendar.id && <CheckCircle size={20} weight="fill" />}
            </button>
          </li>
        ))}
      </ul>

      <button className="btn" type="button" onClick={confirm} disabled={!picked || state === "saving"}>
        {state === "saving" ? "Saving…" : "Use this calendar"}
      </button>
    </div>
  );
}
