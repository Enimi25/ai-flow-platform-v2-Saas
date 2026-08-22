import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { safeRecord } from "@/lib/activity";
import { connectMetaAccounts } from "@/lib/content/meta";

/**
 * One token in, both channels connected.
 *
 * Finding a Page id and the Instagram account behind it by hand means digging
 * through the Graph Explorer, and it is where most people give up. Meta already
 * knows both, so they are asked for rather than typed.
 */
export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { accessToken } = (await request.json().catch(() => ({}))) as { accessToken?: string };
  if (!accessToken) return NextResponse.json({ error: "Paste the access token." }, { status: 400 });

  const companyId = session.companyId ?? "preview";

  let connected: { channel: string; account: string }[];
  try {
    connected = await connectMetaAccounts(companyId, accessToken);
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Facebook refused that token." }, { status: 400 });
  }

  safeRecord({
    companyId,
    kind: "channel.discovered",
    level: "success",
    title: `Connected ${connected.map((entry) => entry.channel).join(" and ")}`,
    detail: connected.map((entry) => entry.account).join(" · "),
  });

  return NextResponse.json({
    connected,
    pages: [],
  });
}
