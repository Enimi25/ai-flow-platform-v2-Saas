import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { getSession } from "@/lib/session";
import { ConfirmClient } from "./confirm-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Confirm calendar | AI FLOW" };

export default async function ConfirmCalendarPage() {
  const session = await getSession();
  return (
    <AppShell active="calendar" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>One last step</h1>
            <p>Pick the calendar customers should be booked into.</p>
          </div>
        </header>
        <ConfirmClient />
      </div>
    </AppShell>
  );
}
