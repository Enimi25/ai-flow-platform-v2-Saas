import type { Metadata } from "next";
import { headers } from "next/headers";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { InstallClient } from "./install-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Install the widget | AI FLOW" };

export default async function InstallPage() {
  const session = await getSession();
  const head = await headers();
  const host = head.get("host") ?? "localhost:3000";
  const origin = `${head.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https")}://${host}`;

  return (
    <AppShell active="install" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Install the widget</h1>
            <p>One line on your site and the agent starts answering customers.</p>
          </div>
          <span className={styles.badge}>{session ? "Workspace active" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/install" />}
        <InstallClient companyId={session?.companyId ?? "preview"} origin={origin} />
      </div>
    </AppShell>
  );
}
