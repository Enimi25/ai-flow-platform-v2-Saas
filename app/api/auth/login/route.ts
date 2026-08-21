import { NextResponse } from "next/server";
import { setSession } from "@/lib/session";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  let body: unknown;
  try { body = await request.json(); } catch { return NextResponse.json({ message: "Invalid request." }, { status: 400 }); }
  const data = body as Record<string, unknown>;
  const email = typeof data?.email === "string" ? data.email.trim().toLowerCase().slice(0, 254) : "";
  const password = typeof data?.password === "string" ? data.password.slice(0, 256) : "";
  if (!emailPattern.test(email) || password.length < 8) return NextResponse.json({ message: "Enter a valid email and password." }, { status: 422 });

  const legacyBase = process.env.LEGACY_API_BASE_URL?.replace(/\/$/, "");
  if (!legacyBase) return NextResponse.json({ message: "Account login is not connected yet." }, { status: 503 });

  let upstream: Response;
  try {
    upstream = await fetch(`${legacyBase}/login-api`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return NextResponse.json({ message: "The account service is unavailable. Try again shortly." }, { status: 502 });
  }

  const result = await upstream.json().catch(() => null) as null | { error?: string; email?: string; role?: string; companyId?: string; company_id?: string };
  if (!upstream.ok || !result || result.error || !result.email || !result.role) {
    return NextResponse.json({ message: result?.error || "Email or password is incorrect." }, { status: 401 });
  }

  try {
    await setSession({ email: result.email, role: result.role, companyId: result.companyId || result.company_id || null });
  } catch {
    return NextResponse.json({ message: "Secure session is not configured." }, { status: 503 });
  }
  return NextResponse.json({ ok: true, role: result.role });
}
