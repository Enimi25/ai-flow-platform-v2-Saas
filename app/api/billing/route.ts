import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listLeads } from "@/lib/leads/store";
import { listPosts } from "@/lib/content/store";
import { listBookings } from "@/lib/booking/store";
import { listConversations } from "@/lib/conversations/store";
import { isStripeReady } from "@/lib/booking/stripe";

const PLANS = [
  {
    id: "website",
    name: "Website Agent",
    priceCents: 3900,
    blurb: "An agent on your site that answers, captures leads and books.",
    includes: ["Website chat", "Lead capture", "Calendar booking"],
    limits: { conversations: 500, posts: 0 },
  },
  {
    id: "connected",
    name: "Connected Sales",
    priceCents: 9900,
    blurb: "Everything above, plus your social channels and the content factory.",
    includes: ["Messenger replies", "Post scheduling", "Shared lead workspace", "Instagram and WhatsApp once verified"],
    limits: { conversations: 3000, posts: 60 },
    featured: true,
  },
  {
    id: "partner",
    name: "Growth Partner",
    priceCents: null,
    blurb: "AI FLOW works the funnel with you and takes a share of what it closes.",
    includes: ["Follow up automation", "Funnel and script tuning", "Custom integrations"],
    limits: { conversations: null, posts: null },
  },
];

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId ?? "preview";

  const [leads, posts, bookings, threads] = await Promise.all([
    listLeads(companyId),
    listPosts(companyId),
    listBookings(companyId),
    listConversations(companyId),
  ]);

  const month = new Date().toISOString().slice(0, 7);
  const inMonth = (iso: string) => iso.slice(0, 7) === month;

  return NextResponse.json({
    plans: PLANS,
    // no subscription exists until Stripe is connected and a plan is bought
    current: null,
    paymentsReady: isStripeReady(),
    usage: {
      month,
      conversations: threads.filter((thread) => inMonth(thread.lastAt)).length,
      leads: leads.filter((lead) => inMonth(lead.createdAt)).length,
      postsPublished: posts.filter((post) => post.status === "published" && post.publishedAt && inMonth(post.publishedAt)).length,
      bookingsPaid: bookings.filter((booking) => booking.status === "paid" && inMonth(booking.createdAt)).length,
    },
  });
}
