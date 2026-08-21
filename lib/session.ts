import { cookies } from "next/headers";

const COOKIE_NAME = "ai_flow_session";
const THIRTY_DAYS = 60 * 60 * 24 * 30;

export type Session = {
  email: string;
  role: string;
  companyId: string | null;
  expiresAt: number;
};

function getSecret() {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) return null;
  return secret;
}

function encode(value: string) {
  return Buffer.from(value).toString("base64url");
}

function decode(value: string) {
  return Buffer.from(value, "base64url").toString("utf8");
}

async function signingKey(secret: string) {
  return crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

export async function createSessionToken(session: Session) {
  const secret = getSecret();
  if (!secret) throw new Error("SESSION_SECRET must contain at least 32 characters.");
  const payload = encode(JSON.stringify(session));
  const signature = await crypto.subtle.sign("HMAC", await signingKey(secret), new TextEncoder().encode(payload));
  return `${payload}.${Buffer.from(signature).toString("base64url")}`;
}

export async function verifySessionToken(token?: string | null): Promise<Session | null> {
  const secret = getSecret();
  if (!secret || !token) return null;
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  try {
    const valid = await crypto.subtle.verify(
      "HMAC",
      await signingKey(secret),
      Buffer.from(signature, "base64url"),
      new TextEncoder().encode(payload),
    );
    if (!valid) return null;
    const session = JSON.parse(decode(payload)) as Session;
    if (!session.email || !session.role || session.expiresAt <= Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

export async function getSession() {
  const store = await cookies();
  return verifySessionToken(store.get(COOKIE_NAME)?.value);
}

export async function setSession(session: Omit<Session, "expiresAt">) {
  const expiresAt = Date.now() + THIRTY_DAYS * 1000;
  const token = await createSessionToken({ ...session, expiresAt });
  const store = await cookies();
  store.set(COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: THIRTY_DAYS,
    priority: "high",
  });
}

export async function clearSession() {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}
