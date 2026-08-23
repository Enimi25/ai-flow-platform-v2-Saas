import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";

const providers = {
  meta: "META_OAUTH_URL",
  facebook: "FACEBOOK_OAUTH_URL",
  instagram: "INSTAGRAM_OAUTH_URL",
  whatsapp: "WHATSAPP_OAUTH_URL",
  tiktok: "TIKTOK_OAUTH_URL",
} as const;

export async function GET(request: Request, context: RouteContext<"/api/social/connect/[provider]">) {
  const session = await getSession();
  if (!session) return NextResponse.redirect(new URL("/login?returnTo=/social-accounts&reason=session", request.url));
  const { provider } = await context.params;
  if (!(provider in providers)) return NextResponse.json({ message: "Unknown provider." }, { status: 404 });
  const envKey = providers[provider as keyof typeof providers];
  const oauthUrl = provider === "tiktok"
    ? "https://www.tiktok.com/v2/auth/authorize/"
    : provider === "meta"
      ? "https://www.facebook.com/v21.0/dialog/oauth"
    : process.env[envKey];
  if (!oauthUrl) return NextResponse.redirect(new URL(`/social-accounts?setup=${provider}`, request.url));

  const state = randomBytes(24).toString("base64url");
  const store = await cookies();
  store.set("ai_flow_oauth_state", state, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 600 });
  const destination = new URL(oauthUrl);
  destination.searchParams.set("state", state);
  if (provider === "tiktok") {
    const clientKey = process.env.TIKTOK_CLIENT_KEY;
    const redirectUri = process.env.TIKTOK_REDIRECT_URI;
    if (!clientKey || !redirectUri) {
      return NextResponse.redirect(new URL("/social-accounts?setup=tiktok", request.url));
    }
    destination.searchParams.set("client_key", clientKey);
    destination.searchParams.set("response_type", "code");
    destination.searchParams.set("scope", "user.info.basic,video.upload");
    destination.searchParams.set("redirect_uri", redirectUri);
  }
  if (provider === "meta") {
    const clientId = process.env.FACEBOOK_CLIENT_ID;
    const redirectUri = process.env.FACEBOOK_REDIRECT_URI;
    if (!clientId || !redirectUri) {
      return NextResponse.redirect(new URL("/social-accounts?setup=meta", request.url));
    }
    destination.searchParams.set("client_id", clientId);
    destination.searchParams.set("redirect_uri", redirectUri);
    destination.searchParams.set("response_type", "code");
    destination.searchParams.set("scope", "pages_show_list,pages_read_engagement,pages_manage_posts,pages_manage_metadata,pages_messaging,instagram_basic,instagram_content_publish,instagram_manage_messages");
  }
  return NextResponse.redirect(destination);
}
