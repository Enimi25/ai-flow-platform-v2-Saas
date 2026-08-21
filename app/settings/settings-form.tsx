"use client";

import { useEffect, useState } from "react";
import { Buildings, Robot, FloppyDisk } from "@phosphor-icons/react";
import { INDUSTRIES, TONES, GOALS, type Settings } from "@/lib/settings/options";
import s from "./settings.module.css";

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

      <div className={s.actions}>
        <button className="btn" type="submit" disabled={saving || !canEdit}>
          <FloppyDisk weight="fill" /> {canEdit ? (saving ? "Saving…" : "Save settings") : "Sign in to edit"}
        </button>
        <span className={s.note}>{note}</span>
      </div>
    </form>
  );
}
