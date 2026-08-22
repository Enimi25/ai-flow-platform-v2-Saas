import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { connectMetaAccounts } from "@/lib/content/meta";
import { safeRecord } from "@/lib/activity";

function returnTo(request: Request, status: string) {
  return NextResponse.redirect(new URL(`/social-accounts?meta=${encodeURIComponent(status)}`, request.url));
}

export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.redirect(new URL("/login?returnTo=/social-accounts&reason=session", request.url));

  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const providerError = url.searchParams.get("error");
  const store = await cookies();
  const expectedState = store.get("ai_flow_oauth_state")?.value;
  store.delete("ai_flow_oauth_state");

  if (providerError) return returnTo(request, providerError);
  if (!code || !state || !expectedState || state !== expectedState) return returnTo(request, "invalid_state");

  const clientId = process.env.FACEBOOK_CLIENT_ID;
  const clientSecret = process.env.FACEBOOK_CLIENT_SECRET;
  const redirectUri = process.env.FACEBOOK_REDIRECT_URI;
  if (!clientId || !clientSecret || !redirectUri) return returnTo(request, "not_configured");

  const tokenUrl = new URL("https://graph.facebook.com/v21.0/oauth/access_token");
  tokenUrl.searchParams.set("client_id", clientId);
  tokenUrl.searchParams.set("client_secret", clientSecret);
  tokenUrl.searchParams.set("redirect_uri", redirectUri);
  tokenUrl.searchParams.set("code", code);
  const tokenResponse = await fetch(tokenUrl, { cache: "no-store" });
  const token = await tokenResponse.json().catch(() => ({})) as { access_token?: string; error?: { message?: string } };
  if (!tokenResponse.ok || !token.access_token) return returnTo(request, token.error?.message ?? "token_exchange_failed");

  const companyId = session.companyId ?? "preview";
  try {
    const connected = await connectMetaAccounts(companyId, token.access_token);
    safeRecord({ companyId, kind: "channel.connected", level: "success", title: "Facebook and Instagram connected", detail: connected.map((item) => item.account).join(" · ") });
    return returnTo(request, connected.some((item) => item.channel === "instagram") ? "connected" : "facebook_connected");
  } catch (error) {
    return returnTo(request, error instanceof Error ? error.message : "account_discovery_failed");
  }
}
