import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { ConnectionsClient } from "./connections-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Connections | AI FLOW" };

export default async function SocialAccountsPage() {
  const session = await getSession();
  return (
    <AppShell active="social" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Connections</h1>
            <p>Attach your own accounts. Posts and replies then go out from them, not from ours.</p>
          </div>
          <span className={styles.badge}>{session ? "Workspace active" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/social-accounts" />}
        <ConnectionsClient canEdit={Boolean(session)} />
      </div>
    </AppShell>
  );
}
