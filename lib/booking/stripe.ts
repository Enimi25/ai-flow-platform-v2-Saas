import { timingSafeEqual } from "node:crypto";

/**
 * Checkout Sessions only. Card details are entered on Stripe's own pages and
 * never touch this server.
 */
const API = "https://api.stripe.com/v1";

export class StripeNotConfigured extends Error {
  constructor(public readonly missing: string[]) {
    super(`Stripe is not connected. Missing: ${missing.join(", ")}`);
    this.name = "StripeNotConfigured";
  }
}

function secretKey() {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new StripeNotConfigured(["STRIPE_SECRET_KEY"]);
  return key;
}

export function isStripeReady() {
  return Boolean(process.env.STRIPE_SECRET_KEY && process.env.STRIPE_WEBHOOK_SECRET);
}

export async function createCheckout(input: {
  bookingId: string;
  service: string;
  amountCents: number;
  currency: string;
  customerEmail: string;
  successUrl: string;
  cancelUrl: string;
}) {
  const body = new URLSearchParams({
    mode: "payment",
    success_url: input.successUrl,
    cancel_url: input.cancelUrl,
    customer_email: input.customerEmail,
    "line_items[0][quantity]": "1",
    "line_items[0][price_data][currency]": input.currency,
    "line_items[0][price_data][unit_amount]": String(input.amountCents),
    "line_items[0][price_data][product_data][name]": input.service,
    "metadata[bookingId]": input.bookingId,
    // the slot is only held for a short while, so the session must not outlive it
    expires_at: String(Math.floor(Date.now() / 1000) + 30 * 60),
  });

  const response = await fetch(`${API}/checkout/sessions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${secretKey()}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });

  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message ?? "Stripe refused to open a checkout session.");
  return payload as { id: string; url: string };
}

/**
 * Verifies the Stripe-Signature header. Anyone can POST to a webhook URL, so an
 * unverified payload must never be trusted to mark a booking paid.
 */
export async function verifyWebhook(rawBody: string, header: string | null) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) throw new StripeNotConfigured(["STRIPE_WEBHOOK_SECRET"]);
  if (!header) throw new Error("Missing Stripe signature.");

  const parts = Object.fromEntries(
    header.split(",").map((piece) => piece.split("=") as [string, string]),
  );
  const timestamp = parts.t;
  const signature = parts.v1;
  if (!timestamp || !signature) throw new Error("Malformed Stripe signature.");

  // reject replays of an old, valid payload
  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(age) || age > 300) throw new Error("Stripe signature is too old.");

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`${timestamp}.${rawBody}`));
  const expected = Buffer.from(digest).toString("hex");

  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new Error("Stripe signature does not match.");
  }

  return JSON.parse(rawBody) as { type: string; data: { object: Record<string, unknown> } };
}
