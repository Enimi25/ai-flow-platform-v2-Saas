import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";

export async function GET(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.redirect(new URL("/login?returnTo=/calendar&reason=session", request.url));
  // Calendar consent uses exactly the same safe Google OAuth flow as sign-in.
  // Keeping a second opaque OAuth URL in the environment made the Calendar
  // button look connected while doing nothing on a fresh deployment.
  return NextResponse.redirect(new URL("/api/auth/google?next=/calendar/confirm", request.url));
}
