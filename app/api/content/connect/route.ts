import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { saveConnection, removeConnection, connectionsFor } from "@/lib/content/connections";
import { CHANNELS, type Channel } from "@/lib/content/types";
import { safeRecord } from "@/lib/activity";

export async function GET() {
  const session = await getSession();
  return NextResponse.json({ connections: await connectionsFor(session?.companyId ?? "preview") });
}

/** Attaches a workspace's own account so its posts stop using the platform's. */
export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await request.json().catch(() => ({}))) as Record<string, string>;
  if (!CHANNELS.includes(body.channel as Channel)) {
    return NextResponse.json({ error: "Unknown channel." }, { status: 400 });
  }
  if (!body.accessToken) {
    return NextResponse.json({ error: "An access token is required." }, { status: 400 });
  }

  const companyId = session.companyId ?? "preview";
  await saveConnection({
    companyId,
    channel: body.channel as Channel,
    accountId: body.accountId ?? "",
    accessToken: body.accessToken,
    accountName: body.accountName,
  });

  safeRecord({
    companyId,
    kind: "channel.connected",
    level: "success",
    title: `${body.channel} connected`,
    detail: body.accountName || body.accountId || undefined,
  });

  return NextResponse.json({ ok: true });
}

export async function DELETE(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { channel } = (await request.json().catch(() => ({}))) as { channel?: Channel };
  if (!channel || !CHANNELS.includes(channel)) {
    return NextResponse.json({ error: "Unknown channel." }, { status: 400 });
  }

  const companyId = session.companyId ?? "preview";
  await removeConnection(companyId, channel);
  safeRecord({ companyId, kind: "channel.disconnected", level: "info", title: `${channel} disconnected` });
  return NextResponse.json({ ok: true });
}
