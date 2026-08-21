import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import { SessionBanner } from "@/components/session-banner";
import { getSession } from "@/lib/session";
import { CalendarClient } from "./calendar-client";
import styles from "@/components/workspace-page.module.css";

export const metadata: Metadata = { title: "Calendar | AI FLOW" };

export default async function CalendarPage() {
  const session = await getSession();
  return (
    <AppShell active="calendar" session={session}>
      <div className={styles.page}>
        <header className={styles.heading}>
          <div>
            <h1>Calendar</h1>
            <p>Appointments the agent booked and paid for, newest first.</p>
          </div>
          <span className={styles.badge}>{session ? "Live" : "Preview mode"}</span>
        </header>
        {!session && <SessionBanner returnTo="/calendar" />}
        <CalendarClient />
      </div>
    </AppShell>
  );
}
