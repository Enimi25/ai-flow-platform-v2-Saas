import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { ContentClient } from "./content-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Content | AI FLOW" };

export default async function ContentPage() {
  const session = await getSession();
  return (
    <AppShell active="content" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Content</h1>
            <p>Write once, schedule it, and let the workspace publish to each channel on time.</p>
          </div>
          <span className={styles.badge}>{session ? "Workspace active" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/content" />}
        <ContentClient canPost={Boolean(session)} />
      </div>
    </AppShell>
  );
}
