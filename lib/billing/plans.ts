export const BILLING_PLANS = [
  {
    id: "website",
    name: "Website Agent",
    priceCents: 3900,
    currency: "usd",
    blurb: "An agent on your site that answers, captures leads and books.",
    includes: ["Website chat", "Lead capture", "Calendar booking"],
    limits: { conversations: 500, posts: 0 },
  },
  {
    id: "connected",
    name: "Connected Sales",
    priceCents: 9900,
    currency: "usd",
    blurb: "Everything above, plus your social channels and the content factory.",
    includes: ["Messenger replies", "Post scheduling", "Shared lead workspace", "Instagram and WhatsApp once verified"],
    limits: { conversations: 3000, posts: 60 },
    featured: true,
  },
] as const;

export type BillingPlan = (typeof BILLING_PLANS)[number];

export function billingPlan(planId: string) {
  return BILLING_PLANS.find((plan) => plan.id === planId) ?? null;
}
