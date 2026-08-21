import { createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { forgetVisitor } from "@/lib/privacy/forget";
import { safeRecord } from "@/lib/activity";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Meta's data deletion callback.
 *
 * When somebody removes the app, Meta posts a signed request here and expects a
 * URL where that person can check the deletion happened, plus a code to track
 * it by. Answering it is a condition of keeping API access, and the deletion has
 * to be real: everything we hold that came from that person goes.
 */

/** base64url, which Meta uses and Buffer does not decode by that name reliably. */
function decode(part: string) {
  return Buffer.from(part.replace(/-/g, "+").replace(/_/g, "/"), "base64");
}

function readSignedRequest(signed: string, secret: string) {
  const [signature, payload] = signed.split(".", 2);
  if (!signature || !payload) return null;

  const expected = createHmac("sha256", secret).update(payload).digest();
  const given = decode(signature);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;

  try {
    return JSON.parse(decode(payload).toString("utf8")) as { user_id?: string; algorithm?: string };
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  const secret = process.env.META_APP_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "Not configured." }, { status: 500 });
  }

  const form = await request.formData().catch(() => null);
  const signed = form?.get("signed_request");
  if (typeof signed !== "string") {
    return NextResponse.json({ error: "Missing signed_request." }, { status: 400 });
  }

  const data = readSignedRequest(signed, secret);
  if (!data?.user_id) {
    return NextResponse.json({ error: "Bad signature." }, { status: 401 });
  }

  const removed = await forgetVisitor(data.user_id).catch(() => 0);

  safeRecord({
    companyId: "preview",
    kind: "privacy.deleted",
    level: "info",
    title: "Data deletion request honoured",
    detail: `${removed} record${removed === 1 ? "" : "s"} removed for a Meta user who left.`,
  });

  const origin = process.env.PUBLIC_SITE_URL || new URL(request.url).origin;

  // Meta shows this URL to the person so they can confirm it happened
  return NextResponse.json({
    url: `${origin}/data-deletion?id=${encodeURIComponent(data.user_id)}`,
    confirmation_code: data.user_id,
  });
}
