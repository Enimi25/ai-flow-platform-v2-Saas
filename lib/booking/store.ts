import path from "node:path";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";

export type BookingStatus = "held" | "paid" | "released" | "failed";

export type Booking = {
  id: string;
  companyId: string;
  ownerEmail: string;
  customerName: string;
  customerEmail: string;
  startsAt: string;
  endsAt: string;
  service: string;
  amountCents: number;
  currency: string;
  status: BookingStatus;
  /** a held slot expires if the customer never finishes checkout */
  holdUntil: string;
  stripeSessionId?: string;
  calendarEventId?: string;
  calendarLink?: string;
  error?: string;
  createdAt: string;
};

const FILE = path.join(process.cwd(), ".data", "bookings.json");
export const HOLD_MINUTES = 15;

const readAll = () => readJson<Booking[]>(FILE, []);

const writeAll = (items: Booking[]) => writeJson(FILE, items);

export async function listBookings(companyId: string) {
  return (await readAll())
    .filter((booking) => booking.companyId === companyId)
    .sort((a, b) => a.startsAt.localeCompare(b.startsAt));
}

export function saveBooking(booking: Booking) {
  // saveBooking
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const index = all.findIndex((entry) => entry.id === booking.id);
  if (index === -1) all.push(booking);
  else all[index] = booking;
  await writeAll(all);
  return booking;
  });
}

export async function bookingBySession(sessionId: string) {
  return (await readAll()).find((booking) => booking.stripeSessionId === sessionId) ?? null;
}

/** A slot is taken if something already holds or owns that exact time. */
export async function slotTaken(companyId: string, startsAt: string, now = new Date()) {
  return (await readAll()).some(
    (booking) =>
      booking.companyId === companyId &&
      booking.startsAt === startsAt &&
      (booking.status === "paid" ||
        (booking.status === "held" && new Date(booking.holdUntil) > now)),
  );
}

/** Frees slots whose checkout was abandoned. */
export function releaseExpired(now = new Date()) {
  // releaseExpired
  return withFileLock(FILE, async () => {
  const all = await readAll();
  let released = 0;
  const next = all.map((booking) => {
    if (booking.status === "held" && new Date(booking.holdUntil) <= now) {
      released += 1;
      return { ...booking, status: "released" as const };
    }
    return booking;
  });
  if (released) await writeAll(next);
  return released;
  });
}
