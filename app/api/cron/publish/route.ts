import { NextResponse } from "next/server";
import { runDue } from "@/lib/content/runner";

/**
 * Called by the scheduler, not by a browser. Point a Render Cron Job at:
 *   curl -H "Authorization: Bearer $CRON_SECRET" https://<host>/api/cron/publish
 */
export async function POST(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "CRON_SECRET is not set." }, { status: 503 });
  }
  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "Not authorised." }, { status: 401 });
  }

  const result = await runDue();
  return NextResponse.json({
    picked: result.picked,
    published: result.published,
    failed: result.failed,
  });
}

export const GET = POST;
