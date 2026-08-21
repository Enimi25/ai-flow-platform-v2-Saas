import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { BillingClient } from "./billing-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Billing | AI FLOW" };

export default async function BillingPage() {
  const session = await getSession();
  return (
    <AppShell active="billing" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Billing</h1>
            <p>What the workspace used this month, and what a plan costs.</p>
          </div>
          <span className={styles.badge}>{session ? "Workspace active" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/billing" />}
        <BillingClient />
      </div>
    </AppShell>
  );
}
