import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { AnalyticsClient } from "./analytics-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Analytics | AI FLOW" };

export default async function AnalyticsPage() {
  const session = await getSession();
  return (
    <AppShell active="analytics" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Analytics</h1>
            <p>Counted from what actually happened in this workspace, not a sample.</p>
          </div>
          <span className={styles.badge}>{session ? "Live" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/analytics" />}
        <AnalyticsClient />
      </div>
    </AppShell>
  );
}
