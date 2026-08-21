"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, LinkSimple, Trash, ArrowSquareOut } from "@phosphor-icons/react";
import s from "./connections.module.css";

type Row = { channel: "facebook" | "instagram" | "tiktok"; connected: boolean; accountName: string | null; connectedAt: string | null };

const META = {
  facebook: {
    label: "Facebook Page",
    blurb: "Replies in Messenger and posts to your Page.",
    idLabel: "Page ID",
    where: "Meta for Developers, Graph API Explorer: pick your Page, then copy the Page Access Token.",
    doc: "https://developers.facebook.com/tools/explorer/",
  },
  instagram: {
    label: "Instagram Business",
    blurb: "Publishes posts and answers direct messages.",
    idLabel: "Instagram user ID",
    where: "The account must be Business and linked to the Page. The token is the same Page Access Token.",
    doc: "https://developers.facebook.com/docs/instagram-api/getting-started",
  },
  tiktok: {
    label: "TikTok",
    blurb: "Publishes videos through the Content Posting API.",
    idLabel: "Open ID",
    where: "TikTok for Developers, your app, Content Posting API. The app has to pass review before it can post publicly.",
    doc: "https://developers.tiktok.com/doc/content-posting-api-get-started",
  },
} as const;

export function ConnectionsClient({ canEdit }: { canEdit: boolean }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [open, setOpen] = useState<Row["channel"] | null>(null);
  const [accountId, setAccountId] = useState("");
  const [token, setToken] = useState("");
  const [accountName, setAccountName] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    const response = await fetch("/api/content/connect");
    if (response.ok) setRows((await response.json()).connections);
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function connect(event: React.FormEvent) {
    event.preventDefault();
    if (!open) return;
    setBusy(true);
    setNote("");
    const response = await fetch("/api/content/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel: open, accountId, accessToken: token, accountName }),
    });
    const data = await response.json();
    setBusy(false);
    if (!response.ok) return setNote(data.error ?? "Could not connect that.");
    setOpen(null);
    setAccountId("");
    setToken("");
    setAccountName("");
    void load();
  }

  async function disconnect(channel: Row["channel"]) {
    setBusy(true);
    await fetch("/api/content/connect", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel }),
    });
    setBusy(false);
    void load();
  }

  return (
    <div className={s.wrap}>
      <ul className={s.list}>
        {rows.map((row) => {
          const meta = META[row.channel];
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
                <button type="button" className={s.ghost} onClick={() => disconnect(row.channel)} disabled={busy || !canEdit}>
                  <Trash size={16} /> Disconnect
                </button>
              ) : (
                row.channel === "tiktok" ? (
                  <a className="btn btn-sm" href="/api/social/connect/tiktok" aria-disabled={!canEdit} onClick={(event) => { if (!canEdit) event.preventDefault(); }}>
                    <LinkSimple size={16} weight="bold" /> Connect
                  </a>
                ) : (
                  <button type="button" className="btn btn-sm" onClick={() => setOpen(row.channel)} disabled={!canEdit}>
                    <LinkSimple size={16} weight="bold" /> Connect
                  </button>
                )
              )}
            </li>
          );
        })}
      </ul>

      {open && open !== "tiktok" && (
        <form className={s.form} onSubmit={connect}>
          <h2>Connect {META[open].label}</h2>
          <p className={s.where}>
            {META[open].where}{" "}
            <a href={META[open].doc} target="_blank" rel="noreferrer">Open the docs <ArrowSquareOut size={13} /></a>
          </p>

          <label htmlFor="account-id">{META[open].idLabel}</label>
          <input id="account-id" value={accountId} onChange={(e) => setAccountId(e.target.value)} placeholder="1234567890" />

          <label htmlFor="account-name">Account name, so you recognise it later</label>
          <input id="account-name" value={accountName} onChange={(e) => setAccountName(e.target.value)} placeholder="AI FLOW" />

          <label htmlFor="token">Access token</label>
          <input id="token" type="password" value={token} onChange={(e) => setToken(e.target.value)} required autoComplete="off" />
          <p className={s.hint}>Stored encrypted. It is never shown again after saving.</p>

          <div className={s.actions}>
            <button className="btn" type="submit" disabled={busy}>{busy ? "Connecting…" : "Connect"}</button>
            <button type="button" className={s.ghost} onClick={() => setOpen(null)}>Cancel</button>
            <span className={s.note}>{note}</span>
          </div>
        </form>
      )}
    </div>
  );
}
