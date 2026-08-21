import { NextResponse } from "next/server";
import { setSession } from "@/lib/session";
import { verifyAccount } from "@/lib/accounts/store";
import { workspaceFor } from "@/lib/workspace/store";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request." }, { status: 400 });
  }

  const data = body as Record<string, unknown>;
  const email = typeof data?.email === "string" ? data.email.trim().toLowerCase().slice(0, 254) : "";
  const password = typeof data?.password === "string" ? data.password.slice(0, 256) : "";
  if (!emailPattern.test(email) || password.length < 8) {
    return NextResponse.json({ message: "Enter a valid email and a password of at least 8 characters." }, { status: 422 });
  }

  // Accounts live here now. The old build proxied every sign-in to an external
  // service that was never connected, so both doors were locked.
  const account = await verifyAccount(email, password);
  if (account) {
    const workspace = await workspaceFor(account.email);
    try {
      await setSession({ email: account.email, role: account.role, companyId: workspace.companyId });
    } catch {
      return NextResponse.json({ message: "Secure session is not configured." }, { status: 503 });
    }
    return NextResponse.json({ ok: true, role: account.role });
  }

  // A legacy install can still point at its old account service.
  const legacyBase = process.env.LEGACY_API_BASE_URL?.replace(/\/$/, "");
  if (legacyBase) {
    try {
      const upstream = await fetch(`${legacyBase}/login-api`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
        cache: "no-store",
        signal: AbortSignal.timeout(10_000),
      });
      const result = (await upstream.json().catch(() => null)) as null | {
        error?: string; email?: string; role?: string; companyId?: string; company_id?: string;
      };
      if (upstream.ok && result?.email && result.role && !result.error) {
        await setSession({
          email: result.email,
          role: result.role,
          companyId: result.companyId || result.company_id || null,
        });
        return NextResponse.json({ ok: true, role: result.role });
      }
    } catch {
      // fall through to the same wrong-credentials answer
    }
  }

  return NextResponse.json({ message: "Email or password is incorrect." }, { status: 401 });
}
