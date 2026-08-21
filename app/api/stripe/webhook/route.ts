import { NextResponse } from "next/server";
import { verifyWebhook } from "@/lib/booking/stripe";
import { bookingBySession, saveBooking } from "@/lib/booking/store";
import { createEvent } from "@/lib/google/calendar";
import { safeRecord } from "@/lib/activity";

/**
 * The only trusted signal that money arrived. The browser redirect after
 * checkout is not: the customer can close the tab before it fires.
 */
export async function POST(request: Request) {
  const raw = await request.text();

  let event;
  try {
    event = await verifyWebhook(raw, request.headers.get("stripe-signature"));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Rejected." },
      { status: 400 },
    );
  }

  if (event.type !== "checkout.session.completed") {
    return NextResponse.json({ ignored: event.type });
  }

  const session = event.data.object as { id: string; payment_status?: string };
  if (session.payment_status && session.payment_status !== "paid") {
    return NextResponse.json({ ignored: "unpaid" });
  }

  const booking = await bookingBySession(session.id);
  if (!booking) return NextResponse.json({ ignored: "unknown booking" });
  if (booking.status === "paid") return NextResponse.json({ ok: true, already: true });

  const paid = await saveBooking({ ...booking, status: "paid" });

  safeRecord({
    companyId: paid.companyId,
    kind: "booking.paid",
    level: "success",
    title: `Payment received from ${paid.customerEmail}`,
    detail: `${paid.service}, ${(paid.amountCents / 100).toFixed(2)} ${paid.currency.toUpperCase()}`,
  });

  // money is in, so the slot goes into the owner's calendar
  try {
    const created = await createEvent(paid.ownerEmail, {
      summary: `${paid.service} — ${paid.customerName || paid.customerEmail}`,
      description: `Booked through AI FLOW and paid via Stripe.`,
      startsAt: paid.startsAt,
      endsAt: paid.endsAt,
      attendeeEmail: paid.customerEmail,
    });
    await saveBooking({ ...paid, calendarEventId: created.id, calendarLink: created.htmlLink });
    safeRecord({
      companyId: paid.companyId,
      kind: "calendar.created",
      level: "success",
      title: "Appointment written to the calendar",
      detail: new Date(paid.startsAt).toLocaleString(),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Calendar write failed.";
    await saveBooking({ ...paid, error: message });
    safeRecord({
      companyId: paid.companyId,
      kind: "calendar.failed",
      level: "error",
      title: "Paid, but the calendar event failed",
      detail: message,
    });
  }

  return NextResponse.json({ ok: true });
}
