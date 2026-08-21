import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { LeadsClient } from "./leads-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Leads | AI FLOW" };

export default async function LeadsPage() {
  const session = await getSession();
  return (
    <AppShell active="leads" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Leads</h1>
            <p>Every visitor who left a way to reach them, newest first.</p>
          </div>
          <span className={styles.badge}>{session ? "Live" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/leads" />}
        <LeadsClient canEdit={Boolean(session)} />
      </div>
    </AppShell>
  );
}
