import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { ActivityClient } from "./activity-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Activity | AI FLOW" };

export default async function ActivityPage() {
  const session = await getSession();
  return (
    <AppShell active="activity" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Activity</h1>
            <p>Everything the workspace does, in the order it happened.</p>
          </div>
          <span className={styles.badge}>{session ? "Live" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/activity" />}
        <ActivityClient />
      </div>
    </AppShell>
  );
}
