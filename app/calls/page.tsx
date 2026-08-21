import { getSession } from "@/lib/session";
import { AppShell } from "@/components/app-shell";
import { CallsClient } from "./calls-client";
import s from "./calls.module.css";

export const metadata = { title: "Calls | AI FLOW" };
export const dynamic = "force-dynamic";

export default async function CallsPage() {
  const session = await getSession();

  return (
    <AppShell active="calls" session={session}>
      <div className={s.head}>
        <div>
          <p className="eyebrow">Voice</p>
          <h1 className="h1">Calls</h1>
          <p className="body">
            Everyone who left a number and has not been called back, with a brief written from
            their own conversation.
          </p>
        </div>
        <span className={s.badge}>VIP</span>
      </div>

      <CallsClient signedIn={Boolean(session)} />
    </AppShell>
  );
}
