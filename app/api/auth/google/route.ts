import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { consentUrl, GoogleNotConfigured } from "@/lib/google/oauth";

const STATE_COOKIE = "ai_flow_oauth_state";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const next = url.searchParams.get("next");
  const returnTo = next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";

  try {
    const state = `${crypto.randomUUID()}|${returnTo}`;
    const store = await cookies();
    store.set(STATE_COOKIE, state, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 600,
    });
    return NextResponse.redirect(consentUrl(state));
  } catch (error) {
    if (error instanceof GoogleNotConfigured) {
      // say exactly what is missing instead of a bare "not configured"
      return NextResponse.json(
        {
          error: "Google sign in is not connected yet.",
          missing: error.missing,
          fix: "Add these to the service environment, then restart it.",
        },
        { status: 503 },
      );
    }
    throw error;
  }
}
