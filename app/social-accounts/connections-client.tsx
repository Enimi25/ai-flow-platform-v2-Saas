"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, LinkSimple, Trash, ArrowSquareOut, ShieldCheck } from "@phosphor-icons/react";
import s from "./connections.module.css";

type Row = { channel: "facebook" | "instagram" | "tiktok" | "whatsapp"; connected: boolean; accountName: string | null; connectedAt: string | null };

const META_CHANNELS = new Set<Row["channel"]>(["facebook", "instagram"]);
const COPY = {
  facebook: { label: "Facebook Page", blurb: "Replies to Messenger and publishes to your Page." },
  instagram: { label: "Instagram Business", blurb: "Publishes posts and helps with direct messages." },
  tiktok: { label: "TikTok", blurb: "Publishes videos through the Content Posting API." },
  whatsapp: { label: "WhatsApp", blurb: "Replies to messages through WhatsApp Business." },
} as const;

export function ConnectionsClient({ canEdit }: { canEdit: boolean }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState<Row["channel"] | "meta" | null>(null);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/content/connect");
    if (response.ok) setRows((await response.json()).connections);
  }, []);

  useEffect(() => {
    void load();
    const params = new URLSearchParams(window.location.search);
    const status = params.get("meta") || params.get("tiktok") || params.get("whatsapp");
    if (status === "connected") setNote("Connected. AI FLOW can now use this account.");
    else if (status && status !== "not_configured") setNote("Connection was not finished. Try again and approve the requested access.");
  }, [load]);

  const metaReady = rows.some((row) => META_CHANNELS.has(row.channel) && row.connected);

  async function disconnect(channel: Row["channel"]) {
    setBusy(channel);
    await fetch("/api/content/connect", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel }),
    });
    setBusy(null);
    void load();
  }

  return (
    <div className={s.wrap}>
      <section className={s.oneTap} aria-label="Connect Meta accounts">
        <div className={s.oneTapCopy}>
          <span className={s.oneTapIcon}><LinkSimple size={22} weight="bold" /></span>
          <div>
            <h2>Connect Facebook and Instagram in one step</h2>
            <p>Sign in with Meta, choose your Page, and AI FLOW finds the linked Instagram Business account automatically.</p>
          </div>
        </div>
        {metaReady ? (
          <span className={s.ready}><CheckCircle size={17} weight="fill" /> Meta connected</span>
        ) : (
          <a className="btn" href="/api/social/connect/meta" aria-disabled={!canEdit} onClick={(event) => { if (!canEdit) event.preventDefault(); setBusy("meta"); }}>
            <LinkSimple size={16} weight="bold" /> {busy === "meta" ? "Opening Meta…" : "Connect Meta"}
          </a>
        )}
        <p className={s.oneTapNote}><ShieldCheck size={16} weight="fill" /> You approve access directly with Meta. Passwords never reach AI FLOW.</p>
      </section>

      {note && <p className={s.notice} role="status">{note}</p>}

      <ul className={s.list}>
        {rows.map((row) => {
          const meta = COPY[row.channel];
          const isMeta = META_CHANNELS.has(row.channel);
          return (
            <li key={row.channel} data-on={row.connected || undefined}>
              <div className={s.info}>
                <div className={s.title}>
                  <b>{meta.label}</b>
                  <span className={row.connected ? s.on : s.off}>
                    {row.connected ? <><CheckCircle size={14} weight="fill" /> Connected</> : "Not connected"}
                  </span>
                </div>
                <p>{meta.blurb}</p>
                {row.connected && row.accountName && <p className={s.account}>{row.accountName}</p>}
              </div>
              {row.connected ? (
                <button type="button" className={s.ghost} onClick={() => disconnect(row.channel)} disabled={busy !== null || !canEdit}>
                  <Trash size={16} /> Disconnect
                </button>
              ) : row.channel === "tiktok" || row.channel === "whatsapp" ? (
                <a className="btn btn-sm" href={`/api/social/connect/${row.channel}`} aria-disabled={!canEdit} onClick={(event) => { if (!canEdit) event.preventDefault(); setBusy(row.channel); }}>
                  <ArrowSquareOut size={16} weight="bold" /> {busy === row.channel ? `Opening ${COPY[row.channel].label}…` : "Connect"}
                </a>
              ) : <span className={s.groupHint}>{isMeta ? "Connect with Meta above" : ""}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
