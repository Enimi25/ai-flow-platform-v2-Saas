"use client";

import { useEffect, useState } from "react";
import { Buildings, CalendarCheck, MegaphoneSimple, Robot, FloppyDisk } from "@phosphor-icons/react";
import { INDUSTRIES, TONES, GOALS, DAY_KEYS, type DayKey, type Settings } from "@/lib/settings/options";
import s from "./settings.module.css";

const DAY_LABEL: Record<DayKey, string> = {
  mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday",
  fri: "Friday", sat: "Saturday", sun: "Sunday",
};

/** A short list beats a thousand-entry dropdown nobody scrolls. */
const ZONES = [
  "Europe/London", "Europe/Dublin", "Europe/Lisbon", "Europe/Madrid", "Europe/Paris",
  "Europe/Berlin", "Europe/Rome", "Europe/Warsaw", "Europe/Prague", "Europe/Athens",
  "Europe/Kyiv", "Europe/Moscow", "Europe/Istanbul", "Asia/Dubai", "Asia/Almaty",
  "Asia/Tashkent", "Asia/Bangkok", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney",
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Sao_Paulo",
];

export function SettingsForm({ canEdit }: { canEdit: boolean }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    (async () => {
      const response = await fetch("/api/settings");
      const data = await response.json();
      setSettings(data.settings);
    })();
  }, []);

  function set<K extends keyof Settings>(key: K, value: Settings[K]) {
    setSettings((current) => (current ? { ...current, [key]: value } : current));
  }

  /** One weekday at a time, because a business shuts one day and not the rest. */
  function setDay(day: DayKey, next: { open: string; close: string } | null) {
    setSettings((current) =>
      current ? { ...current, openingHours: { ...current.openingHours, [day]: next } } : current,
    );
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!settings) return;
    setSaving(true);
    setNote("");
    const response = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    const data = await response.json();
    setSaving(false);
    setNote(response.ok ? "Saved." : data.error ?? "Could not save.");
    if (response.ok) setSettings(data.settings);
  }

  if (!settings) return <p className={s.muted}>Loading…</p>;

  return (
    <form className={s.board} onSubmit={save}>
      <section className={s.panel}>
        <div className={s.panelHead}>
          <Buildings size={26} weight="fill" />
          <h2>Company profile</h2>
        </div>

        <label htmlFor="company-name">Company name</label>
        <input id="company-name" value={settings.companyName} onChange={(e) => set("companyName", e.target.value)} placeholder="AI FLOW" />

        <label htmlFor="industry">Industry</label>
        <select id="industry" value={settings.industry} onChange={(e) => set("industry", e.target.value)}>
          {INDUSTRIES.map((item) => <option key={item}>{item}</option>)}
        </select>

        <label htmlFor="website">Website</label>
        <input id="website" type="url" value={settings.website} onChange={(e) => set("website", e.target.value)} placeholder="https://example.com" />

        <label htmlFor="phone">Business phone</label>
        <input id="phone" value={settings.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+41 79 000 00 00" />

        <p className={s.hint}>Workspace id <code>{settings.companyId}</code></p>
      </section>

      <section className={s.panel}>
        <div className={s.panelHead}>
          <Robot size={26} weight="fill" />
          <h2>Assistant</h2>
        </div>

        <label htmlFor="assistant-name">Assistant name</label>
        <input id="assistant-name" value={settings.assistantName} onChange={(e) => set("assistantName", e.target.value)} />

        <div className={s.pair}>
          <div>
            <label htmlFor="tone">Tone</label>
            <select id="tone" value={settings.tone} onChange={(e) => set("tone", e.target.value)}>
              {TONES.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="goal">Goal</label>
            <select id="goal" value={settings.goal} onChange={(e) => set("goal", e.target.value)}>
              {GOALS.map((item) => <option key={item}>{item}</option>)}
            </select>
          </div>
        </div>

        <label htmlFor="welcome">Opening line</label>
        <textarea id="welcome" rows={2} value={settings.welcome} onChange={(e) => set("welcome", e.target.value)} />

        <label htmlFor="lead-question">How it asks for contact details</label>
        <input id="lead-question" value={settings.leadQuestion} onChange={(e) => set("leadQuestion", e.target.value)} />

        <label htmlFor="description">What the business does</label>
        <textarea
          id="description"
          rows={5}
          value={settings.businessDescription}
          onChange={(e) => set("businessDescription", e.target.value)}
          placeholder="Services, prices, opening hours, who the ideal customer is. The agent answers from this."
        />
        <p className={s.hint}>The more concrete this is, the fewer wrong answers the agent gives.</p>
      </section>

      <section className={s.panel}>
        <div className={s.panelHead}>
          <CalendarCheck size={26} weight="fill" />
          <h2>When you are open</h2>
        </div>
        <p className={s.hint}>
          The agent offers appointments from these hours and nothing else. Get them wrong and it
          will book somebody for a day you are shut.
        </p>

        <label className={s.toggle}>
          <input
            type="checkbox"
            checked={settings.bookingEnabled}
            onChange={(e) => set("bookingEnabled", e.target.checked)}
          />
          <span><b>Let the agent book appointments</b><small>Turn this off and it only takes contact details.</small></span>
        </label>

        <div className={s.days}>
          {DAY_KEYS.map((day) => {
            const hours = settings.openingHours[day];
            return (
              <div key={day} className={s.day} data-shut={!hours}>
                <label className={s.dayName}>
                  <input
                    type="checkbox"
                    checked={Boolean(hours)}
                    onChange={(e) => setDay(day, e.target.checked ? { open: "09:00", close: "18:00" } : null)}
                  />
                  <span>{DAY_LABEL[day]}</span>
                </label>
                {hours ? (
                  <div className={s.dayTimes}>
                    <input
                      type="time"
                      value={hours.open}
                      aria-label={`${DAY_LABEL[day]} opens`}
                      onChange={(e) => setDay(day, { ...hours, open: e.target.value })}
                    />
                    <em>to</em>
                    <input
                      type="time"
                      value={hours.close}
                      aria-label={`${DAY_LABEL[day]} closes`}
                      onChange={(e) => setDay(day, { ...hours, close: e.target.value })}
                    />
                  </div>
                ) : (
                  <span className={s.shut}>Closed</span>
                )}
              </div>
            );
          })}
        </div>

        <div className={s.pair}>
          <div>
            <label htmlFor="timezone">Your timezone</label>
            <select id="timezone" value={settings.timezone} onChange={(e) => set("timezone", e.target.value)}>
              {ZONES.map((zone) => <option key={zone} value={zone}>{zone.replace("_", " ")}</option>)}
            </select>
            <p className={s.hint}>Every time the agent says out loud is in this zone.</p>
          </div>
          <div>
            <label htmlFor="slot">How long one appointment takes</label>
            <select
              id="slot"
              value={settings.slotMinutes}
              onChange={(e) => set("slotMinutes", Number(e.target.value))}
            >
              {[15, 20, 30, 45, 60, 90, 120].map((n) => (
                <option key={n} value={n}>{n} minutes</option>
              ))}
            </select>
            <p className={s.hint}>Slots are cut to this length, back to back.</p>
          </div>
        </div>
      </section>

      <section className={s.panel}>
        <div className={s.panelHead}>
          <MegaphoneSimple size={26} weight="fill" />
          <h2>The content factory</h2>
        </div>
        <p className={s.hint}>
          Writes and publishes posts from what you wrote above, to the accounts you have connected.
          Nothing is queued for a channel that is not linked.
        </p>

        <label className={s.toggle}>
          <input
            type="checkbox"
            checked={settings.contentAuto}
            onChange={(e) => set("contentAuto", e.target.checked)}
          />
          <span><b>Post for me automatically</b><small>The queue tops itself up. You can read and delete anything before it goes.</small></span>
        </label>

        <label htmlFor="per-week">How many posts a week, per channel</label>
        <input
          id="per-week"
          type="range"
          min={1}
          max={21}
          value={settings.contentPerWeek}
          onChange={(e) => set("contentPerWeek", Number(e.target.value))}
        />
        <p className={s.rangeValue}>
          <b>{settings.contentPerWeek}</b> a week
          <span>{settings.contentPerWeek >= 7 ? ` — about ${Math.round((settings.contentPerWeek / 7) * 10) / 10} a day` : ""}</span>
        </p>
      </section>

      <div className={s.actions}>
        <button className="btn" type="submit" disabled={saving || !canEdit}>
          <FloppyDisk weight="fill" /> {canEdit ? (saving ? "Saving…" : "Save settings") : "Sign in to edit"}
        </button>
        <span className={s.note}>{note}</span>
      </div>
    </form>
  );
}
