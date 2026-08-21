import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { exchangeCode, profileFrom, saveGrant } from "@/lib/google/oauth";
import { setSession } from "@/lib/session";
import { workspaceFor } from "@/lib/workspace/store";
import { safeRecord } from "@/lib/activity";

const STATE_COOKIE = "ai_flow_oauth_state";

function back(request: Request, path: string, reason?: string) {
  const target = new URL(path, new URL(request.url).origin);
  if (reason) target.searchParams.set("reason", reason);
  return NextResponse.redirect(target);
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const store = await cookies();
  const expected = store.get(STATE_COOKIE)?.value;
  store.delete(STATE_COOKIE);

  if (url.searchParams.get("error")) return back(request, "/login", "google-denied");

  const state = url.searchParams.get("state");
  const code = url.searchParams.get("code");
  if (!code || !state || !expected || state !== expected) {
    return back(request, "/login", "google-state");
  }

  const returnTo = state.split("|")[1] || "/dashboard";

  try {
    const tokens = await exchangeCode(code);
    const profile = await profileFrom(tokens.access_token);

    // Only the first consent returns a refresh token. Without one the calendar
    // cannot be written to later, so the user has to be sent back through.
    if (tokens.refresh_token) {
      await saveGrant(profile.email, tokens.refresh_token);
    }

    // first sign in creates this customer's own workspace
    const workspace = await workspaceFor(profile.email);
    await setSession({ email: profile.email, role: "owner", companyId: workspace.companyId });

    safeRecord({
      companyId: workspace.companyId,
      kind: "auth.google",
      level: "success",
      title: `Signed in as ${profile.email}`,
      detail: tokens.refresh_token ? "Google account and calendar connected" : "Signed in, calendar already connected",
    });

    return NextResponse.redirect(new URL(returnTo, url.origin));
  } catch {
    return back(request, "/login", "google-failed");
  }
}
