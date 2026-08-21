import { DAY_KEYS, type OpeningHours, type Settings } from "@/lib/settings/options";
import { listBookings } from "./store";

/**
 * Free appointment times, worked out from opening hours and what is already
 * booked.
 *
 * Times are stored and compared as UTC instants, but a business thinks in wall
 * clock: "Tuesday at ten" means ten in its own timezone, whatever the server is
 * set to. Everything below converts one to the other rather than assuming they
 * agree, because for most of the year they do not.
 */

/** Minutes to add to a UTC instant to read it as wall clock in `zone`. */
function offsetMinutes(instant: Date, zone: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: zone,
    hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).formatToParts(instant);

  const get = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);
  const asUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second"));
  return (asUtc - instant.getTime()) / 60_000;
}

/** The UTC instant for a wall-clock time on a given local date in `zone`. */
function instantFor(year: number, month: number, day: number, hour: number, minute: number, zone: string) {
  const guess = Date.UTC(year, month - 1, day, hour, minute);
  // one correction is enough except on the hour a DST change lands, where the
  // second pass settles it
  const first = guess - offsetMinutes(new Date(guess), zone) * 60_000;
  const second = guess - offsetMinutes(new Date(first), zone) * 60_000;
  return new Date(second);
}

/** Local calendar date in `zone`, as numbers. */
function localParts(instant: Date, zone: string) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: zone, hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit", weekday: "short",
  }).formatToParts(instant);
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    year: Number(get("year")),
    month: Number(get("month")),
    day: Number(get("day")),
    weekday: get("weekday").toLowerCase().slice(0, 3),
  };
}

function minutesOf(clock: string) {
  const [hour, minute] = clock.split(":").map(Number);
  return (hour || 0) * 60 + (minute || 0);
}

export type Slot = { startsAt: string; label: string };

export async function freeSlots(
  settings: Settings,
  options: { days?: number; limit?: number; now?: Date; perDay?: number } = {},
): Promise<Slot[]> {
  if (!settings.bookingEnabled) return [];

  const zone = settings.timezone || "Europe/London";
  const length = Math.max(15, Math.min(240, settings.slotMinutes || 60));
  const days = options.days ?? 10;
  const limit = options.limit ?? 8;
  // Offering six times on one Saturday hides every other day, and a customer
  // who wants Sunday then picks a Saturday slot by its hour.
  const perDay = options.perDay ?? Math.max(2, Math.ceil(limit / 3));
  const now = options.now ?? new Date();

  const booked = new Set(
    (await listBookings(settings.companyId).catch(() => []))
      .filter((booking) => booking.status !== "released" && booking.status !== "failed")
      .map((booking) => new Date(booking.startsAt).getTime()),
  );

  // an hour of notice, so the agent never offers a time that is already passing
  const earliest = now.getTime() + 60 * 60_000;
  const hours: OpeningHours = settings.openingHours;
  const found: Slot[] = [];

  for (let dayOffset = 0; dayOffset < days && found.length < limit; dayOffset += 1) {
    const cursor = new Date(now.getTime() + dayOffset * 86_400_000);
    const { year, month, day, weekday } = localParts(cursor, zone);

    const key = DAY_KEYS.find((candidate) => candidate === weekday);
    const open = key ? hours[key] : null;
    if (!open) continue;

    const from = minutesOf(open.open);
    const until = minutesOf(open.close);

    let onThisDay = 0;
    for (let at = from; at + length <= until && found.length < limit && onThisDay < perDay; at += length) {
      const startsAt = instantFor(year, month, day, Math.floor(at / 60), at % 60, zone);
      if (startsAt.getTime() < earliest) continue;
      if (booked.has(startsAt.getTime())) continue;

      onThisDay += 1;
      found.push({
        startsAt: startsAt.toISOString(),
        label: new Intl.DateTimeFormat("en-GB", {
          timeZone: zone,
          weekday: "long", day: "numeric", month: "long",
          hour: "2-digit", minute: "2-digit", hour12: false,
        }).format(startsAt),
      });
    }
  }

  return found;
}

/** Whether a specific instant is a real, still-free opening. */
export async function slotIsFree(settings: Settings, startsAt: string) {
  const wanted = new Date(startsAt).getTime();
  if (Number.isNaN(wanted)) return false;
  const slots = await freeSlots(settings, { days: 30, limit: 500 });
  return slots.some((slot) => new Date(slot.startsAt).getTime() === wanted);
}
