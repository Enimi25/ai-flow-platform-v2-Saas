import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { billingPlan } from "@/lib/billing/plans";
import { stripeClient, StripeNotConfigured } from "@/lib/booking/stripe";
import { publicUrl } from "@/lib/public-url";

export async function POST(request: Request) {
  const session = await getSession();
  if (!session?.companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = await request.json().catch(() => null) as { planId?: string } | null;
  const plan = body?.planId ? billingPlan(body.planId) : null;
  if (!plan) return NextResponse.json({ error: "Choose an available plan." }, { status: 400 });

  try {
    const origin = publicUrl("/", request).origin;
    const checkout = await stripeClient().checkout.sessions.create({
      mode: "subscription",
      success_url: `${origin}/billing?success=1`,
      cancel_url: `${origin}/billing?cancelled=1`,
      customer_email: session.email,
      client_reference_id: session.companyId,
      line_items: [{
        quantity: 1,
        price_data: {
          currency: plan.currency,
          unit_amount: plan.priceCents,
          recurring: { interval: "month" },
          product_data: { name: `AI FLOW — ${plan.name}` },
        },
      }],
      metadata: { kind: "subscription", companyId: session.companyId, planId: plan.id },
      subscription_data: { metadata: { companyId: session.companyId, planId: plan.id } },
      integration_identifier: `ai_flow_billing_${crypto.randomUUID().replaceAll("-", "").slice(0, 8)}`,
    });
    if (!checkout.url) throw new Error("Stripe did not return a checkout URL.");
    return NextResponse.json({ checkoutUrl: checkout.url });
  } catch (error) {
    if (error instanceof StripeNotConfigured) {
      return NextResponse.json({ error: "Payments are not connected yet.", missing: error.missing }, { status: 503 });
    }
    return NextResponse.json({ error: error instanceof Error ? error.message : "Could not start checkout." }, { status: 502 });
  }
}
