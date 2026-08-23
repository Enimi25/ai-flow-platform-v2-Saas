import { createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { connectionByAccount } from "@/lib/content/connections";
import { answerMessage } from "@/lib/messaging/reply";
import { sendWhatsAppMessage } from "@/lib/messaging/whatsapp";
import { safeRecord } from "@/lib/activity";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const seen = new Map<string, number>();
const SEEN_FOR = 10 * 60 * 1000;

function alreadyHandled(id: string) {
  const now = Date.now();
  for (const [key, at] of seen) if (now - at > SEEN_FOR) seen.delete(key);
  if (seen.has(id)) return true;
  seen.set(id, now);
  return false;
}

function signatureMatches(raw: string, header: string | null) {
  const secret = process.env.META_APP_SECRET;
  if (!secret || !header?.startsWith("sha256=")) return false;
  const expected = Buffer.from(createHmac("sha256", secret).update(raw).digest("hex"));
  const given = Buffer.from(header.slice(7));
  return expected.length === given.length && timingSafeEqual(expected, given);
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const expected = process.env.WHATSAPP_VERIFY_TOKEN ?? process.env.META_VERIFY_TOKEN;
  const challenge = url.searchParams.get("hub.challenge");
  if (!expected) return NextResponse.json({ error: "WHATSAPP_VERIFY_TOKEN is not set." }, { status: 500 });
  if (url.searchParams.get("hub.mode") !== "subscribe" || url.searchParams.get("hub.verify_token") !== expected || !challenge) {
    return new NextResponse("Forbidden", { status: 403 });
  }
  return new NextResponse(challenge, { headers: { "Content-Type": "text/plain" } });
}

type Change = {
  value?: {
    metadata?: { phone_number_id?: string };
    messages?: Array<{ id?: string; from?: string; type?: string; text?: { body?: string } }>;
  };
};

export async function POST(request: Request) {
  const raw = await request.text();
  if (!signatureMatches(raw, request.headers.get("x-hub-signature-256"))) return new NextResponse("Bad signature", { status: 401 });

  let payload: { entry?: Array<{ changes?: Change[] }> };
  try { payload = JSON.parse(raw); } catch { return new NextResponse("Bad payload", { status: 400 }); }

  for (const entry of payload.entry ?? []) for (const change of entry.changes ?? []) {
    const account = change.value?.metadata?.phone_number_id;
    for (const message of change.value?.messages ?? []) {
      const text = message.type === "text" ? message.text?.body?.trim() : undefined;
      if (!account || !message.from || !text || (message.id && alreadyHandled(message.id))) continue;
      void handle({ account, from: message.from, text });
    }
  }
  return NextResponse.json({ received: true });
}

async function handle(input: { account: string; from: string; text: string }) {
  try {
    const link = await connectionByAccount(input.account, "whatsapp");
    const companyId = link?.companyId ?? process.env.WHATSAPP_DEFAULT_COMPANY_ID;
    if (!companyId) throw new Error("WhatsApp number is not linked to a workspace.");
    const reply = await answerMessage({ companyId, from: input.from, text: input.text, source: "whatsapp" });
    await sendWhatsAppMessage({ companyId, to: input.from, text: reply });
  } catch (error) {
    safeRecord({
      companyId: process.env.WHATSAPP_DEFAULT_COMPANY_ID ?? "preview",
      kind: "message.whatsapp",
      level: "error",
      title: "Could not answer on WhatsApp",
      detail: error instanceof Error ? error.message : String(error),
    });
  }
}
