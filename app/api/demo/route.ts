import { NextResponse } from "next/server";
import { sendEmail, EmailNotConfigured, isEmailReady } from "@/lib/email/send";
import { proposalEmail } from "@/lib/email/proposal";
import { safeRecord } from "@/lib/activity";
import { houseCompanyId } from "@/lib/workspace/store";
import { previewConversation } from "@/lib/email/preview";
import { enrol } from "@/lib/email/sequence";
import { captureLead } from "@/lib/leads/store";

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: Request) {
  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > 8_000) return NextResponse.json({ message: "Request is too large." }, { status: 413 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request." }, { status: 400 });
  }
  if (!body || typeof body !== "object") return NextResponse.json({ message: "Invalid request." }, { status: 400 });

  const data = body as Record<string, unknown>;
  if (data.website) return NextResponse.json({ ok: true }); // honeypot

  const name = typeof data.name === "string" ? data.name.trim().slice(0, 80) : "";
  const email = typeof data.email === "string" ? data.email.trim().toLowerCase().slice(0, 254) : "";
  const question = typeof data.question === "string" ? data.question.trim().slice(0, 1_000) : "";
  if (name.length < 2) {
    return NextResponse.json({ message: "Please enter your name (at least 2 characters)." }, { status: 422 });
  }
  if (!emailPattern.test(email)) {
    return NextResponse.json({ message: "Please enter a valid business email address." }, { status: 422 });
  }
  if (question.length < 3) {
    return NextResponse.json({ message: "Please add a short description of your business." }, { status: 422 });
  }

  const house = await houseCompanyId();
  // their own agent, answering their own customers, before they have paid anything
  const preview = await previewConversation(question).catch(() => []);
  const origin = new URL(request.url).origin;
  const siteUrl = process.env.PUBLIC_SITE_URL || origin;

  await captureLead({
    companyId: house,
    name,
    email,
    message: question,
    source: "demo",
  }).catch(() => {});

  // three more touches over three weeks, stopped the moment they reply
  await enrol({
    email,
    name,
    business: question,
    companyId: house,
  }).catch(() => null);

  safeRecord({
    companyId: house,
    kind: "demo.requested",
    level: "info",
    title: `Demo requested by ${email}`,
    detail: question.slice(0, 160),
  });

  // hand the lead to whatever the team already uses, if anything is wired up
  const webhook = process.env.DEMO_WEBHOOK_URL;
  if (webhook) {
    await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, question }),
      signal: AbortSignal.timeout(8_000),
    }).catch(() => {});
  }

  if (!isEmailReady()) {
    return NextResponse.json(
      {
        ok: true,
        emailed: false,
        message: "Request received. The proposal email is not connected yet.",
        missing: ["RESEND_API_KEY", "EMAIL_FROM"].filter((key) => !process.env[key]),
      },
      { status: 200 },
    );
  }

  try {
    await sendEmail({
      to: email,
      subject: `${name}, we built your agent`,
      replyTo: process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com",
      html: proposalEmail({
        name,
        question,
        preview,
        siteUrl,
        videoUrl: process.env.DEMO_VIDEO_URL,
        contactEmail: process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com",
        contactPhone: process.env.CONTACT_PHONE,
        companyLegalName: process.env.COMPANY_LEGAL_NAME,
      }),
    });

    safeRecord({
      companyId: house,
      kind: "demo.proposal_sent",
      level: "success",
      title: `Proposal emailed to ${email}`,
    });

    return NextResponse.json({ ok: true, emailed: true });
  } catch (error) {
    const missing = error instanceof EmailNotConfigured ? error.missing : undefined;
    safeRecord({
      companyId: house,
      kind: "demo.proposal_failed",
      level: "error",
      title: `Proposal to ${email} did not send`,
      detail: error instanceof Error ? error.message : undefined,
    });
    return NextResponse.json({ ok: true, emailed: false, missing }, { status: 200 });
  }
}
