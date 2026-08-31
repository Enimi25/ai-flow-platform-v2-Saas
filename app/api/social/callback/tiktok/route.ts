import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { safeRecord } from "@/lib/activity";
import { saveConnection } from "@/lib/content/connections";
import { getSession } from "@/lib/session";
import { publicUrl } from "@/lib/public-url";

type TokenResponse = {
  access_token?: string;
  open_id?: string;
  refresh_token?: string;
  expires_in?: number;
  error?: string;
  error_description?: string;
};

type UserResponse = {
  data?: { user?: { open_id?: string; display_name?: string } };
  error?: { code?: string; message?: string };
};

function returnTo(request: Request, status: string) {
  return NextResponse.redirect(publicUrl(`/social-accounts?tiktok=${encodeURIComponent(status)}`, request));
}

export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.redirect(publicUrl("/login?returnTo=/social-accounts&reason=session", request));

  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const providerError = url.searchParams.get("error");
  const store = await cookies();
  const expectedState = store.get("ai_flow_oauth_state")?.value;
  store.delete("ai_flow_oauth_state");

  if (providerError) return returnTo(request, providerError);
  if (!code || !state || !expectedState || state !== expectedState) return returnTo(request, "invalid_state");

  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
  const redirectUri = process.env.TIKTOK_REDIRECT_URI;
  if (!clientKey || !clientSecret || !redirectUri) return returnTo(request, "not_configured");

  const tokenResponse = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      code,
      grant_type: "authorization_code",
      redirect_uri: redirectUri,
    }),
    cache: "no-store",
  });
  const token = (await tokenResponse.json().catch(() => ({}))) as TokenResponse;
  if (!tokenResponse.ok || !token.access_token) return returnTo(request, token.error ?? "token_exchange_failed");

  const userResponse = await fetch(
    "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name",
    { headers: { Authorization: `Bearer ${token.access_token}` }, cache: "no-store" },
  );
  const profile = (await userResponse.json().catch(() => ({}))) as UserResponse;
  const user = profile.data?.user;
  if (!userResponse.ok || profile.error?.code && profile.error.code !== "ok") {
    return returnTo(request, profile.error?.code ?? "profile_fetch_failed");
  }

  const companyId = session.companyId ?? "preview";
  await saveConnection({
    companyId,
    channel: "tiktok",
    accountId: user?.open_id ?? token.open_id ?? "",
    accessToken: token.access_token,
    accountName: user?.display_name ?? "TikTok",
  });
  safeRecord({
    companyId,
    kind: "channel.connected",
    level: "success",
    title: "tiktok connected",
    detail: user?.display_name,
  });

  return returnTo(request, "connected");
}
