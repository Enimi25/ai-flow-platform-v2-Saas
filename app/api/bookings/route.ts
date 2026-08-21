import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listBookings, releaseExpired } from "@/lib/booking/store";
import { isStripeReady } from "@/lib/booking/stripe";
import { grantFor } from "@/lib/google/oauth";
import { isGoogleReady } from "@/lib/google/oauth";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId ?? "preview";

  await releaseExpired();
  const bookings = await listBookings(companyId);
  const now = new Date();

  const grant = session ? await grantFor(session.email).catch(() => null) : null;

  return NextResponse.json({
    upcoming: bookings.filter((b) => b.status === "paid" && new Date(b.startsAt) >= now),
    past: bookings.filter((b) => b.status === "paid" && new Date(b.startsAt) < now).slice(0, 20),
    held: bookings.filter((b) => b.status === "held"),
    calendar: {
      connected: Boolean(grant),
      calendarId: grant?.calendarId ?? null,
      googleReady: isGoogleReady(),
    },
    paymentsReady: isStripeReady(),
  });
}
