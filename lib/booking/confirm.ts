import { saveBooking, slotTaken, type Booking } from "./store";
import { slotIsFree } from "./slots";
import { safeRecord } from "@/lib/activity";
import type { Settings } from "@/lib/settings/options";

/**
 * The marker the agent writes when a customer settles on a time.
 *
 * It carries the slot's number in the offered list, not a timestamp. Asked for
 * an ISO string the model writes back the human label it just used — "Saturday
 * 22 August at 12:00" — and the booking never happens. A single digit it gets
 * right.
 */
export const BOOK_MARK = /\[\[BOOK:\s*(\d{1,2})\s*\]\]/;

/** Anything marker-shaped, so a malformed one never reaches the customer. */
export const ANY_MARK = /\[\[\s*BOOK\s*:[^\]]*\]\]/gi;

/**
 * Turns an agreed time into a booking.
 *
 * Confirmed, not held: there is no deposit in this path, so nothing has to be
 * paid for the appointment to be real. The slot is re-checked here rather than
 * trusted from the reply — the model proposes, the calendar decides.
 */
export async function confirmBooking(input: {
  settings: Settings;
  startsAt: string;
  customerName?: string;
  customerEmail?: string;
  service?: string;
}) {
  const { settings, startsAt } = input;

  if (!(await slotIsFree(settings, startsAt))) return null;
  if (await slotTaken(settings.companyId, startsAt)) return null;

  const starts = new Date(startsAt);
  const ends = new Date(starts.getTime() + (settings.slotMinutes || 60) * 60_000);

  const booking: Booking = {
    id: crypto.randomUUID(),
    companyId: settings.companyId,
    ownerEmail: "",
    customerName: (input.customerName || "").slice(0, 120),
    customerEmail: (input.customerEmail || "").slice(0, 254),
    startsAt: starts.toISOString(),
    endsAt: ends.toISOString(),
    service: (input.service || "Appointment").slice(0, 120),
    amountCents: 0,
    currency: "eur",
    status: "paid",
    holdUntil: ends.toISOString(),
    createdAt: new Date().toISOString(),
  };

  await saveBooking(booking);

  safeRecord({
    companyId: settings.companyId,
    kind: "booking.created",
    level: "success",
    title: "Appointment booked by the agent",
    detail: `${booking.customerName || "A customer"} · ${new Intl.DateTimeFormat("en-GB", {
      timeZone: settings.timezone || "Europe/London",
      weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(starts)}`,
  });

  return booking;
}

/**
 * The date and time, written so it cannot be misread in any language.
 *
 * The model confirmed one booking as "next day at 13:00" when it had actually
 * taken a Saturday — vague enough that the customer would not have noticed. The
 * authoritative line goes in from here instead of being left to the reply.
 */
export function bookingLine(settings: Settings, startsAt: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: settings.timezone || "Europe/London",
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(new Date(startsAt));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("day")}.${get("month")}.${get("year")}, ${get("hour")}:${get("minute")}`;
}
