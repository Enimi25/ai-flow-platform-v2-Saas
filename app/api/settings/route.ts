import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { defaults, getSettings, saveSettings, type Settings } from "@/lib/settings/store";
import { safeRecord } from "@/lib/activity";

export async function GET() {
  const session = await getSession();
  return NextResponse.json({ settings: await getSettings(session?.companyId ?? "preview") });
}

export async function PUT(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in to change settings." }, { status: 401 });

  const companyId = session.companyId ?? "preview";
  const body = (await request.json().catch(() => ({}))) as Partial<Settings>;
  const current = await getSettings(companyId);

  const text = (value: unknown, fallback: string, max = 400) =>
    typeof value === "string" && value.trim() ? value.trim().slice(0, max) : fallback;

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
