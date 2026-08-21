"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, Copy, Globe, ArrowClockwise, PaperPlaneTilt, Warning } from "@phosphor-icons/react";
import s from "./install.module.css";

const GUIDES = [
  {
    id: "html",
    label: "Plain HTML",
    time: "2 minutes",
    steps: [
      "Open the file every page of the site shares. It is usually index.html, or a template named footer, layout, or base.",
      "Scroll to the very bottom and find the line that reads </body>.",
      "Paste the snippet on its own line directly above </body>.",
      "Save the file and upload it to the server, replacing the old one.",
      "Open the site in a new tab. A chat button appears in the bottom right corner.",
    ],
    gotcha: "If the site has several HTML files, the snippet has to go into each one, unless they all share a single template.",
  },
  {
    id: "wordpress",
    label: "WordPress",
    time: "3 minutes",
    steps: [
      "Sign in to the admin area at yoursite.com/wp-admin.",
      "Go to Plugins, then Add New Plugin, and search for WPCode.",
      "Press Install Now on WPCode, then Activate.",
      "In the left menu open Code Snippets, then Header & Footer.",
      "Paste the snippet into the Footer box, not the Header box.",
      "Press Save Changes at the top of the page.",
    ],
    gotcha: "Do not edit theme files directly. A theme update wipes those changes, and the widget disappears with them.",
  },
  {
    id: "shopify",
    label: "Shopify",
    time: "4 minutes",
    steps: [
      "In the admin open Online Store, then Themes.",
      "On your live theme press the three dots button, then Edit code.",
      "In the Layout folder on the left open theme.liquid.",
      "Press Ctrl+F, or Cmd+F on a Mac, and search for </body>.",
      "Paste the snippet on the line directly above </body>.",
      "Press Save in the top right corner.",
    ],
    gotcha: "This one edits a theme file, so duplicate the theme first: three dots, Duplicate. If anything goes wrong, switch back to the copy.",
  },
  {
    id: "wix",
    label: "Wix",
    time: "2 minutes",
    steps: [
      "Open your site dashboard and go to Settings.",
      "Scroll to Advanced and choose Custom Code.",
      "Press Add Custom Code in the top right.",
      "Paste the snippet into the code box and name it AI FLOW.",
      "Under Add Code to Pages choose All pages, and under Place Code in choose Body - end.",
      "Press Apply, then publish the site.",
    ],
    gotcha: "Custom code needs a paid Wix plan. On the free plan the option is greyed out.",
  },
  {
    id: "webflow",
    label: "Webflow",
    time: "2 minutes",
    steps: [
      "Open the project and press the gear icon for Project Settings.",
      "Open the Custom Code tab.",
      "Paste the snippet into the Footer Code box.",
      "Press Save Changes.",
      "Press Publish in the top right, and confirm the domain.",
    ],
    gotcha: "Custom code only runs on a published site. It will not appear in the Designer preview.",
  },
  {
    id: "tilda",
    label: "Tilda",
    time: "2 minutes",
    steps: [
      "Open the site and press Site Settings.",
      "Choose More, then find HTML code for the BODY section.",
      "Paste the snippet there and press Save.",
      "Return to the page list and press Publish all pages.",
    ],
    gotcha: "One page republished on its own is not enough. Use Publish all pages, otherwise the widget shows on some pages only.",
  },
  {
    id: "squarespace",
    label: "Squarespace",
    time: "2 minutes",
    steps: [
      "Open Settings, then Advanced, then Code Injection.",
      "Paste the snippet into the Footer box.",
      "Press Save in the top left corner.",
    ],
    gotcha: "Code Injection needs a Business plan or higher. On Personal the section is not available.",
  },
];

export function InstallClient({ companyId, origin }: { companyId: string; origin: string }) {
  const [guide, setGuide] = useState(GUIDES[0]);
  const [copied, setCopied] = useState(false);
  const [checking, setChecking] = useState(false);
  const [install, setInstall] = useState<{ installed: boolean; hosts: string[]; lastSeen: string | null } | null>(null);
  const [helper, setHelper] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState("");

  const snippet = `<script src="${origin}/widget.js" data-company-id="${companyId}"></script>`;

  const check = useCallback(async () => {
    setChecking(true);
    const response = await fetch("/api/widget/verify");
    if (response.ok) setInstall(await response.json());
    setChecking(false);
  }, []);

  useEffect(() => {
    void check();
    const timer = window.setInterval(check, 20_000);
    return () => window.clearInterval(timer);
  }, [check]);

  async function copy() {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  }

  async function sendInstructions(event: React.FormEvent) {
    event.preventDefault();
    setSending(true);
    setSent("");
    const response = await fetch("/api/widget/instructions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to: helper, platform: guide.id }),
    });
    const data = await response.json();
    setSending(false);
    setSent(response.ok ? `Sent to ${helper}.` : data.error ?? "Could not send that.");
    if (response.ok) setHelper("");
  }

  return (
    <div className={s.wrap}>
      <section className={s.panel}>
        <h2>Your snippet</h2>
        <p className={s.muted}>
          This line belongs to your workspace only. Leads it captures land in your account and nobody else&apos;s.
        </p>

        <pre className={s.code}><code>{snippet}</code></pre>

        <button type="button" className="btn" onClick={copy}>
          {copied ? <><CheckCircle weight="fill" /> Copied</> : <><Copy weight="fill" /> Copy the snippet</>}
        </button>
      </section>

      <section className={s.panel}>
        <h2>Where it goes</h2>
        <div className={s.tabs} role="tablist">
          {GUIDES.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={guide.id === entry.id}
              data-on={guide.id === entry.id || undefined}
              onClick={() => setGuide(entry)}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <div className={s.guide}>
          <p className={s.time}>About {guide.time}</p>
          <ol className={s.steps}>
            {guide.steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <p className={s.gotcha}><Warning size={17} weight="fill" /> {guide.gotcha}</p>
        </div>

        <form className={s.handoff} onSubmit={sendInstructions}>
          <label htmlFor="helper">Not the one who edits the site? Send it to whoever is.</label>
          <div className={s.handoffRow}>
            <input
              id="helper"
              type="email"
              value={helper}
              onChange={(event) => setHelper(event.target.value)}
              placeholder="developer@example.com"
              required
            />
            <button className="btn" type="submit" disabled={sending}>
              <PaperPlaneTilt weight="fill" /> {sending ? "Sending…" : "Send instructions"}
            </button>
          </div>
          <p className={s.muted}>{sent}</p>
        </form>
      </section>

      <section className={s.panel} data-live={install?.installed || undefined}>
        <div className={s.checkHead}>
          <h2>Is it live?</h2>
          <button type="button" onClick={check} aria-label="Check again" disabled={checking}>
            <ArrowClockwise size={16} weight="bold" />
          </button>
        </div>

        {install?.installed ? (
          <>
            <p className={s.live}><CheckCircle size={20} weight="fill" /> The widget is answering on your site.</p>
            <ul className={s.hosts}>
              {install.hosts.map((host) => (
                <li key={host}><Globe size={16} /> {host}</li>
              ))}
            </ul>
            {install.lastSeen && (
              <p className={s.muted}>Last seen {new Date(install.lastSeen).toLocaleString()}</p>
            )}
          </>
        ) : (
          <p className={s.muted}>
            Nothing has reported in yet. Paste the snippet, open your site once, and this turns green on its own.
          </p>
        )}
      </section>
    </div>
  );
}
