import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { defaults, getSettings, saveSettings, DAY_KEYS, type DayHours, type OpeningHours, type Settings } from "@/lib/settings/store";
import { safeRecord } from "@/lib/activity";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  return NextResponse.json({ settings: await getSettings(companyId) });
}

export async function PUT(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in to change settings." }, { status: 401 });

  const companyId = session.companyId ?? "preview";
  const body = (await request.json().catch(() => ({}))) as Partial<Settings>;
  const current = await getSettings(companyId);

  const text = (value: unknown, fallback: string, max = 400) =>
    typeof value === "string" && value.trim() ? value.trim().slice(0, max) : fallback;

  const clock = (value: unknown) =>
    typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value) ? value : null;

  /** A day is only kept if it opens before it closes; anything else is shut. */
  const day = (value: unknown, fallback: DayHours): DayHours => {
    if (value === null) return null;
    if (!value || typeof value !== "object") return fallback;
    const open = clock((value as Record<string, unknown>).open);
    const close = clock((value as Record<string, unknown>).close);
    if (!open || !close || open >= close) return null;
    return { open, close };
  };

  const openingHours: OpeningHours = { ...current.openingHours };
  if (body.openingHours && typeof body.openingHours === "object") {
    for (const key of DAY_KEYS) {
      openingHours[key] = day(
        (body.openingHours as Record<string, unknown>)[key],
        current.openingHours[key],
      );
    }
  }

  // an unknown timezone would make every offered slot silently wrong
  const zone = typeof body.timezone === "string" ? body.timezone : current.timezone;
  const timezone = (() => {
    try {
      new Intl.DateTimeFormat("en-GB", { timeZone: zone });
      return zone;
    } catch {
      return current.timezone;
    }
  })();

  const next: Settings = {
    ...defaults(companyId),
    ...current,
    companyName: text(body.companyName, current.companyName, 120),
    industry: text(body.industry, current.industry, 60),
    website: text(body.website, current.website, 200),
    phone: text(body.phone, current.phone, 40),
    assistantName: text(body.assistantName, current.assistantName, 40),
    tone: text(body.tone, current.tone, 30),
    goal: text(body.goal, current.goal, 40),
    welcome: text(body.welcome, current.welcome, 300),
    leadQuestion: text(body.leadQuestion, current.leadQuestion, 300),
    businessDescription: text(body.businessDescription, current.businessDescription, 2000),
    openingHours,
    timezone,
    slotMinutes:
      typeof body.slotMinutes === "number" && body.slotMinutes >= 15 && body.slotMinutes <= 240
        ? Math.round(body.slotMinutes)
        : current.slotMinutes,
    bookingEnabled:
      typeof body.bookingEnabled === "boolean" ? body.bookingEnabled : current.bookingEnabled,
    contentAuto: typeof body.contentAuto === "boolean" ? body.contentAuto : current.contentAuto,
    contentPerWeek:
      typeof body.contentPerWeek === "number" && body.contentPerWeek >= 1 && body.contentPerWeek <= 21
        ? Math.round(body.contentPerWeek)
        : current.contentPerWeek,
    companyId,
  };

  const saved = await saveSettings(next);
  safeRecord({
    companyId,
    kind: "settings.saved",
    level: "info",
    title: "Settings updated",
    detail: saved.companyName || undefined,
  });

  return NextResponse.json({ settings: saved });
}
