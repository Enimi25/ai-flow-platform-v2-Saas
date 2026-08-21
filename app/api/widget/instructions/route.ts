import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { sendEmail, isEmailReady } from "@/lib/email/send";
import { installEmail, PLATFORM_STEPS } from "@/lib/email/install-instructions";
import { safeRecord } from "@/lib/activity";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { to, platform } = (await request.json().catch(() => ({}))) as { to?: string; platform?: string };
  if (!to || !emailPattern.test(to)) {
    return NextResponse.json({ error: "Enter a valid email address." }, { status: 422 });
  }

  const origin = new URL(request.url).origin;
  const siteUrl = process.env.PUBLIC_SITE_URL || origin;
  const snippet = `<script src="${siteUrl}/widget.js" data-company-id="${companyId}"></script>`;
  const chosen = platform && platform in PLATFORM_STEPS ? platform : "html";

  if (!isEmailReady()) {
    return NextResponse.json(
      { error: "Email sending is not connected yet.", missing: ["RESEND_API_KEY", "EMAIL_FROM"].filter((k) => !process.env[k]) },
      { status: 503 },
    );
  }

  try {
    await sendEmail({
      to,
      subject: "One line to add to the website",
      html: installEmail({ snippet, platform: chosen, fromName: session?.email ?? "A colleague", siteUrl }),
    });
    safeRecord({
      companyId,
      kind: "widget.instructions_sent",
      level: "info",
      title: `Install instructions sent to ${to}`,
      detail: PLATFORM_STEPS[chosen].label,
    });
    return NextResponse.json({ ok: true });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not send that." },
      { status: 502 },
    );
  }
}
