import { createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { connectionByAccount } from "@/lib/content/connections";
import { answerMessage } from "@/lib/messaging/reply";
import { sendMessage } from "@/lib/messaging/send";
import { safeRecord } from "@/lib/activity";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * Messenger and Instagram inbound messages.
 *
 * Two rules govern this endpoint and both come from Meta. The signature has to
 * be checked, because the URL is public and without it anyone can post a fake
 * customer message and make the assistant reply to a stranger. And the reply
 * has to happen *after* the 200: Meta retries anything slower than a few
 * seconds and disables a webhook that keeps timing out, so the model call runs
 * detached rather than inside the request.
 */

/** Meta redelivers on any hiccup, so the same message arrives more than once. */
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
  if (!secret) return false;
  if (!header?.startsWith("sha256=")) return false;

  const expected = Buffer.from(createHmac("sha256", secret).update(raw).digest("hex"));
  const given = Buffer.from(header.slice(7));
  return expected.length === given.length && timingSafeEqual(expected, given);
}

/** Meta's subscription handshake: echo the challenge, in plain text. */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const mode = url.searchParams.get("hub.mode");
  const token = url.searchParams.get("hub.verify_token");
  const challenge = url.searchParams.get("hub.challenge");

  const expected = process.env.META_VERIFY_TOKEN;
  if (!expected) {
    return NextResponse.json({ error: "META_VERIFY_TOKEN is not set." }, { status: 500 });
  }
  if (mode !== "subscribe" || token !== expected || !challenge) {
    return new NextResponse("Forbidden", { status: 403 });
  }
  return new NextResponse(challenge, {
    status: 200,
    headers: { "Content-Type": "text/plain" },
  });
}

type Messaging = {
  sender?: { id?: string };
  recipient?: { id?: string };
  message?: { mid?: string; text?: string; is_echo?: boolean };
};

type Entry = { id?: string; messaging?: Messaging[] };

export async function POST(request: Request) {
  const raw = await request.text();

  if (!signatureMatches(raw, request.headers.get("x-hub-signature-256"))) {
    return new NextResponse("Bad signature", { status: 401 });
  }

  let payload: { object?: string; entry?: Entry[] };
  try {
    payload = JSON.parse(raw);
  } catch {
    return new NextResponse("Bad payload", { status: 400 });
  }

  const channel = payload.object === "instagram" ? "instagram" : "facebook";

  for (const entry of payload.entry ?? []) {
    for (const event of entry.messaging ?? []) {
      const from = event.sender?.id;
      const text = event.message?.text?.trim();
      const mid = event.message?.mid;

      // echoes are our own replies coming back; everything else here is a
      // delivery receipt, a reaction or an attachment, none of which we answer
      if (!from || !text || event.message?.is_echo) continue;
      if (mid && alreadyHandled(mid)) continue;

      // the account the customer wrote to, which is how we find the workspace
      const account = event.recipient?.id ?? entry.id;
      if (!account) continue;

      void handle({ account, channel, from, text });
    }
  }

  return NextResponse.json({ received: true });
}

async function handle(input: {
  account: string;
  channel: "facebook" | "instagram";
  from: string;
  text: string;
}) {
  try {
    const link = await connectionByAccount(input.account, input.channel);
    if (!link) {
      safeRecord({
        companyId: "preview",
        kind: `message.${input.channel}`,
        level: "warn",
        title: `Message to an unlinked ${input.channel} account`,
        detail: `Account ${input.account} is not connected to any workspace.`,
      });
      return;
    }

    const reply = await answerMessage({
      companyId: link.companyId,
      from: input.from,
      text: input.text,
      source: input.channel,
    });

    await sendMessage({
      companyId: link.companyId,
      channel: input.channel,
      to: input.from,
      text: reply,
    });
  } catch (error) {
    safeRecord({
      companyId: "preview",
      kind: `message.${input.channel}`,
      level: "error",
      title: `Could not answer on ${input.channel}`,
      detail: error instanceof Error ? error.message : String(error),
    });
  }
}
