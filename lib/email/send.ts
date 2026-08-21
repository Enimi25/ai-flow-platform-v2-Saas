export class EmailNotConfigured extends Error {
  constructor(public readonly missing: string[]) {
    super(`Email sending is not connected. Missing: ${missing.join(", ")}`);
    this.name = "EmailNotConfigured";
  }
}

export function isEmailReady() {
  return Boolean(process.env.RESEND_API_KEY && process.env.EMAIL_FROM);
}

/**
 * Resend, because it needs one key and no SMTP handshake. Swapping providers is
 * a change to this function alone.
 */
export async function sendEmail(input: {
  to: string;
  subject: string;
  html: string;
  replyTo?: string;
}) {
  const missing = ["RESEND_API_KEY", "EMAIL_FROM"].filter((name) => !process.env[name]);
  if (missing.length) throw new EmailNotConfigured(missing);

  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: process.env.EMAIL_FROM,
      to: [input.to],
      subject: input.subject,
      html: input.html,
      reply_to: input.replyTo ?? process.env.EMAIL_REPLY_TO ?? undefined,
    }),
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.message ?? `The email provider returned ${response.status}.`);
  }
  return payload as { id: string };
}
