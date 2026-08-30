import { seal, open } from "./crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { dataFile } from "@/lib/data-dir";

const AUTH = "https://accounts.google.com/o/oauth2/v2/auth";
const TOKEN = "https://oauth2.googleapis.com/token";

/**
 * Identity and calendar are requested together, so one consent screen covers
 * signing in and connecting the calendar. There is no second step.
 */
const SCOPES = [
  "openid",
  "https://www.googleapis.com/auth/userinfo.email",
  "https://www.googleapis.com/auth/userinfo.profile",
  "https://www.googleapis.com/auth/calendar.events",
];

export class GoogleNotConfigured extends Error {
  constructor(public readonly missing: string[]) {
    super(`Google sign in is not configured. Missing: ${missing.join(", ")}`);
    this.name = "GoogleNotConfigured";
  }
}

export function googleConfig() {
  const missing = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"].filter(
    (name) => !process.env[name],
  );
  if (missing.length) throw new GoogleNotConfigured(missing);
  return {
    clientId: process.env.GOOGLE_CLIENT_ID as string,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
    redirectUri: process.env.GOOGLE_REDIRECT_URI as string,
  };
}

export function isGoogleReady() {
  try {
    googleConfig();
    return true;
  } catch {
    return false;
  }
}

export function consentUrl(state: string) {
  const { clientId, redirectUri } = googleConfig();
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(" "),
    // both are required to get a refresh token back on the first consent
    access_type: "offline",
    prompt: "consent",
    include_granted_scopes: "true",
    state,
  });
  return `${AUTH}?${params}`;
}

type TokenResponse = {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  id_token?: string;
};

export async function exchangeCode(code: string): Promise<TokenResponse> {
  const { clientId, clientSecret, redirectUri } = googleConfig();
  const response = await fetch(TOKEN, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: redirectUri,
      grant_type: "authorization_code",
    }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error_description ?? "Google refused the authorization code.");
  return payload as TokenResponse;
}

export async function refreshAccessToken(refreshToken: string) {
  const { clientId, clientSecret } = googleConfig();
  const response = await fetch(TOKEN, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: "refresh_token",
    }),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error_description ?? "Could not refresh the Google access token.");
  return payload as TokenResponse;
}

export async function profileFrom(accessToken: string) {
  const response = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error("Google would not return the profile.");
  return (await response.json()) as { email: string; name?: string; sub: string };
}

/* --- stored grants ------------------------------------------------------ */

type Grant = { email: string; refreshToken: string; connectedAt: string; calendarId?: string };
const FILE = dataFile("google-grants.json");

async function readAll(): Promise<Record<string, Grant>> {
  try {
    return JSON.parse(await fs.readFile(FILE, "utf8"));
  } catch {
    return {};
  }
}

export async function saveGrant(email: string, refreshToken: string) {
  const all = await readAll();
  all[email] = { ...all[email], email, refreshToken: seal(refreshToken), connectedAt: new Date().toISOString() };
  await fs.mkdir(path.dirname(FILE), { recursive: true });
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
}

export async function setCalendar(email: string, calendarId: string) {
  const all = await readAll();
  if (!all[email]) throw new Error("No Google grant for that account.");
  all[email] = { ...all[email], calendarId };
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
}

export async function grantFor(email: string) {
  const grant = (await readAll())[email];
  if (!grant) return null;
  return { ...grant, refreshToken: open(grant.refreshToken) };
}
