import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { OverviewClient } from "./overview-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Overview | AI FLOW" };

export default async function DashboardPage() {
  const session = await getSession();
  return (
    <AppShell active="overview" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Overview</h1>
            <p>Where the workspace stands right now.</p>
          </div>
          <span className={styles.badge}>{session ? "Workspace active" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/dashboard" />}
        <OverviewClient />
      </div>
    </AppShell>
  );
}
