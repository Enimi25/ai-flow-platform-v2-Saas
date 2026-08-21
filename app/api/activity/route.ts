import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listEvents } from "@/lib/activity";
import { isGoogleReady } from "@/lib/google/oauth";
import { isStripeReady } from "@/lib/booking/stripe";
import { channelReadiness } from "@/lib/content/publishers";
import { modelStatus } from "@/lib/model";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });
  const channels = await channelReadiness(companyId);

  const steps = [
    { id: "signin", label: "Signed in", done: Boolean(session) },
    { id: "google", label: "Google and calendar connected", done: isGoogleReady() },
    { id: "payments", label: "Payments connected", done: isStripeReady() },
    { id: "social", label: "A social channel connected", done: Object.values(channels).some((c) => c.ready) },
  ];

  return NextResponse.json({
    models: await modelStatus(),
    events: await listEvents(companyId),
    steps,
    progress: Math.round((steps.filter((step) => step.done).length / steps.length) * 100),
  });
}
