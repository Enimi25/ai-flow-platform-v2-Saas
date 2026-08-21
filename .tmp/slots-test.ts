import { freeSlots } from "../lib/booking/slots";
import { defaults } from "../lib/settings/store";

async function main() {
  const base = defaults("test-salon");

  // вторник-воскресенье 10-20, час на клиента, Москва
  const salon = {
    ...base,
    timezone: "Europe/Moscow",
    slotMinutes: 60,
    openingHours: {
      mon: null,
      tue: { open: "10:00", close: "20:00" },
      wed: { open: "10:00", close: "20:00" },
      thu: { open: "10:00", close: "20:00" },
      fri: { open: "10:00", close: "20:00" },
      sat: { open: "10:00", close: "18:00" },
      sun: { open: "12:00", close: "17:00" },
    },
  };

  const now = new Date("2026-08-24T06:00:00Z"); // понедельник, выходной
  const slots = await freeSlots(salon, { now, limit: 6 });
  console.log("понедельник выходной — первые свободные:");
  for (const slot of slots) console.log("  ", slot.label, " (UTC", slot.startsAt + ")");

  const closed = await freeSlots({ ...salon, bookingEnabled: false }, { now });
  console.log("\nзапись выключена:", closed.length, "слотов");

  const sunday = await freeSlots(salon, { now: new Date("2026-08-30T05:00:00Z"), limit: 3 });
  console.log("\nвоскресенье, короткий день 12-17:");
  for (const slot of sunday) console.log("  ", slot.label);
}
main();
