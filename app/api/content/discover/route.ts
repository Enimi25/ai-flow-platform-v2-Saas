import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { saveConnection } from "@/lib/content/connections";
import { safeRecord } from "@/lib/activity";

const GRAPH = "https://graph.facebook.com/v21.0";

type Page = {
  id: string;
  name: string;
  access_token: string;
  instagram_business_account?: { id: string; username?: string };
};

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

  const url = new URL(`${GRAPH}/me/accounts`);
  url.searchParams.set("fields", "id,name,access_token,instagram_business_account{id,username}");
  url.searchParams.set("access_token", accessToken);

  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    return NextResponse.json(
      { error: payload?.error?.message ?? "Facebook refused that token." },
      { status: 400 },
    );
  }

  const pages = (payload?.data ?? []) as Page[];
  if (!pages.length) {
    return NextResponse.json(
      {
        error:
          "That token works, but it manages no Pages. Generate a Page Access Token rather than a User token, and pick your Page.",
      },
      { status: 400 },
    );
  }

  const connected: { channel: string; account: string }[] = [];

  for (const page of pages) {
    // each Page carries its own token, which is the one publishing needs
    await saveConnection({
      companyId,
      channel: "facebook",
      accountId: page.id,
      accessToken: page.access_token || accessToken,
      accountName: page.name,
    });
    connected.push({ channel: "facebook", account: page.name });

    const instagram = page.instagram_business_account;
    if (instagram?.id) {
      await saveConnection({
        companyId,
        channel: "instagram",
        accountId: instagram.id,
        accessToken: page.access_token || accessToken,
        accountName: instagram.username ? `@${instagram.username}` : page.name,
      });
      connected.push({ channel: "instagram", account: instagram.username ?? instagram.id });
    }

    // one workspace publishes to one Page, so the first is the one that counts
    break;
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
    pages: pages.map((page) => ({
      id: page.id,
      name: page.name,
      instagram: page.instagram_business_account?.username ?? null,
    })),
  });
}
