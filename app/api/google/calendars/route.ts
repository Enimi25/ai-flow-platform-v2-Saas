import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listCalendars } from "@/lib/google/calendar";
import { setCalendar } from "@/lib/google/oauth";
import { safeRecord } from "@/lib/activity";

export async function GET() {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });
  try {
    return NextResponse.json(await listCalendars(session.email));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not reach Google." },
      { status: 502 },
    );
  }
}

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { calendarId } = (await request.json().catch(() => ({}))) as { calendarId?: string };
  if (!calendarId) return NextResponse.json({ error: "Pick a calendar." }, { status: 400 });

  try {
    await setCalendar(session.email, calendarId);
    safeRecord({
      companyId: session.companyId ?? "preview",
      kind: "calendar.connected",
      level: "success",
      title: "Calendar confirmed for bookings",
      detail: calendarId,
    });
    return NextResponse.json({ ok: true, calendarId });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not save that choice." },
      { status: 500 },
    );
  }
}
