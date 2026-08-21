import { NextResponse } from "next/server";
import { setSession } from "@/lib/session";
import { createAccount } from "@/lib/accounts/store";
import { workspaceFor } from "@/lib/workspace/store";
import { safeRecord } from "@/lib/activity";
import { adoptPreviewRecords } from "@/lib/workspace/adopt";

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

  if (!emailPattern.test(email)) {
    return NextResponse.json({ message: "That does not look like an email address." }, { status: 422 });
  }
  if (password.length < 8) {
    return NextResponse.json({ message: "Use at least 8 characters." }, { status: 422 });
  }

  const account = await createAccount(email, password);
  if (!account) {
    return NextResponse.json({ message: "There is already an account with that email. Sign in instead." }, { status: 409 });
  }

  const workspace = await workspaceFor(account.email);
  try {
    await setSession({ email: account.email, role: account.role, companyId: workspace.companyId });
  } catch {
    return NextResponse.json({ message: "Secure session is not configured." }, { status: 503 });
  }

  // the platform owner inherits everything the site collected before accounts
  const adopted = account.role === "admin" ? await adoptPreviewRecords(workspace.companyId) : 0;
  if (adopted) {
    safeRecord({
      companyId: workspace.companyId,
      kind: "account.adopted",
      level: "success",
      title: `Recovered ${adopted} records collected before sign-up`,
      detail: "Leads, conversations and activity from the site are now in this workspace.",
    });
  }

  safeRecord({
    companyId: workspace.companyId,
    kind: "account.created",
    level: "success",
    title: "Workspace created",
    detail: account.email,
  });

  return NextResponse.json({ ok: true, role: account.role, companyId: workspace.companyId, adopted });
}
