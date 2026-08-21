import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { ConversationsClient } from "./conversations-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Conversations | AI FLOW" };

export default async function ConversationsPage() {
  const session = await getSession();
  return (
    <AppShell active="conversations" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Conversations</h1>
            <p>What customers actually asked, and how the agent answered.</p>
          </div>
          <span className={styles.badge}>{session ? "Live" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/conversations" />}
        <ConversationsClient />
      </div>
    </AppShell>
  );
}
