import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Public liveness probe. A platform health check (Render's, say) hits this
 * unauthenticated and expects a 2xx, so it must never require a session or
 * touch the disk - it only proves the process is up and serving. Per-account
 * readiness lives behind auth in /api/activity instead.
 */
export async function GET() {
  return NextResponse.json({ ok: true });
}
