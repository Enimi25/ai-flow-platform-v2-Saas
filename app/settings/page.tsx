import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { SettingsForm } from "./settings-form";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Settings | AI FLOW" };

export default async function SettingsPage() {
  const session = await getSession();
  return (
    <AppShell active="settings" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Settings</h1>
            <p>Your company details and how the assistant speaks to customers.</p>
          </div>
          <span className={styles.badge}>{session?.role ?? "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/settings" />}
        <SettingsForm canEdit={Boolean(session)} />
      </div>
    </AppShell>
  );
}
