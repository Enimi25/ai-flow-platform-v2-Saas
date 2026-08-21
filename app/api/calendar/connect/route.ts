import { randomBytes } from "node:crypto";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";

export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.redirect(new URL("/login?returnTo=/calendar&reason=session", request.url));
  const oauthUrl = process.env.GOOGLE_CALENDAR_OAUTH_URL;
  if (!oauthUrl) return NextResponse.redirect(new URL("/calendar?setup=google", request.url));
  const state = randomBytes(24).toString("base64url");
  const store = await cookies();
  store.set("ai_flow_calendar_oauth_state", state, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 600 });
  const destination = new URL(oauthUrl);
  destination.searchParams.set("state", state);
  return NextResponse.redirect(destination);
}
