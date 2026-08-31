import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { HOLD_MINUTES, saveBooking, slotTaken, releaseExpired, type Booking } from "@/lib/booking/store";
import { createCheckout, StripeNotConfigured } from "@/lib/booking/stripe";
import { safeRecord } from "@/lib/activity";
import { publicUrl } from "@/lib/public-url";

export async function POST(request: Request) {
  const session = await getSession();
  const companyId = session?.companyId ?? "preview";

  await releaseExpired();

  const body = (await request.json().catch(() => null)) as Partial<Booking> | null;
  if (!body?.startsAt || !body.customerEmail || !body.service) {
    return NextResponse.json({ error: "Need a slot, a service, and an email." }, { status: 400 });
  }

  const startsAt = new Date(body.startsAt);
  if (Number.isNaN(startsAt.getTime()) || startsAt <= new Date()) {
    return NextResponse.json({ error: "Pick a time in the future." }, { status: 400 });
  }

  if (await slotTaken(companyId, startsAt.toISOString())) {
    return NextResponse.json({ error: "That slot has just been taken." }, { status: 409 });
  }

  const minutes = Number(body.endsAt ? 0 : 60) || 60;
  const booking: Booking = {
    id: crypto.randomUUID(),
    companyId,
    ownerEmail: session?.email ?? "",
    customerName: body.customerName?.slice(0, 120) ?? "",
    customerEmail: body.customerEmail.slice(0, 254),
    startsAt: startsAt.toISOString(),
    endsAt: body.endsAt ?? new Date(startsAt.getTime() + minutes * 60_000).toISOString(),
    service: body.service.slice(0, 140),
    amountCents: Math.max(0, Number(body.amountCents ?? 0)),
    currency: (body.currency ?? "usd").toLowerCase(),
    status: "held",
    holdUntil: new Date(Date.now() + HOLD_MINUTES * 60_000).toISOString(),
    createdAt: new Date().toISOString(),
  };

  const origin = publicUrl("/", request).origin;

  try {
    const checkout = await createCheckout({
      bookingId: booking.id,
      service: booking.service,
      amountCents: booking.amountCents,
      currency: booking.currency,
      customerEmail: booking.customerEmail,
      successUrl: `${origin}/calendar?booked=${booking.id}`,
      cancelUrl: `${origin}/calendar?cancelled=${booking.id}`,
    });
    booking.stripeSessionId = checkout.id;
    await saveBooking(booking);

    safeRecord({
      companyId,
      kind: "booking.held",
      level: "info",
      title: `Slot held for ${booking.customerEmail}`,
      detail: `${booking.service} at ${new Date(booking.startsAt).toLocaleString()}, ${HOLD_MINUTES} minutes to pay`,
    });

    return NextResponse.json({ booking, checkoutUrl: checkout.url }, { status: 201 });
  } catch (error) {
    if (error instanceof StripeNotConfigured) {
      return NextResponse.json(
        { error: "Payments are not connected yet.", missing: error.missing },
        { status: 503 },
      );
    }
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not start checkout." },
      { status: 502 },
    );
  }
}
