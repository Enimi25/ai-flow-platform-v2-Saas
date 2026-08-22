import Stripe from "stripe";

/**
 * Checkout Sessions only. Card details are entered on Stripe's own pages and
 * never touch this server.
 */
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

export function stripeClient() {
  return new Stripe(secretKey(), { maxNetworkRetries: 2 });
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
  return stripeClient().checkout.sessions.create({
    mode: "payment",
    success_url: input.successUrl,
    cancel_url: input.cancelUrl,
    customer_email: input.customerEmail,
    line_items: [{
      quantity: 1,
      price_data: {
        currency: input.currency,
        unit_amount: input.amountCents,
        product_data: { name: input.service },
      },
    }],
    metadata: { bookingId: input.bookingId, kind: "booking" },
    integration_identifier: `ai_flow_booking_${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`,
    // the slot is only held for a short while, so the session must not outlive it
    expires_at: Math.floor(Date.now() / 1000) + 30 * 60,
  });
}

/**
 * Verifies the Stripe-Signature header. Anyone can POST to a webhook URL, so an
 * unverified payload must never be trusted to mark a booking paid.
 */
export async function verifyWebhook(rawBody: string, header: string | null) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) throw new StripeNotConfigured(["STRIPE_WEBHOOK_SECRET"]);
  if (!header) throw new Error("Missing Stripe signature.");

  return stripeClient().webhooks.constructEvent(rawBody, header, secret, 300);
}
