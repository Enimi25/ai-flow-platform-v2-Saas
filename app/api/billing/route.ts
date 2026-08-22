import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listLeads } from "@/lib/leads/store";
import { listPosts } from "@/lib/content/store";
import { listBookings } from "@/lib/booking/store";
import { listConversations } from "@/lib/conversations/store";
import { isStripeReady } from "@/lib/booking/stripe";
import { BILLING_PLANS } from "@/lib/billing/plans";
import { subscriptionFor } from "@/lib/billing/store";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const [leads, posts, bookings, threads, subscription] = await Promise.all([
    listLeads(companyId),
    listPosts(companyId),
    listBookings(companyId),
    listConversations(companyId),
    subscriptionFor(companyId),
  ]);

  const month = new Date().toISOString().slice(0, 7);
  const inMonth = (iso: string) => iso.slice(0, 7) === month;

  return NextResponse.json({
    plans: BILLING_PLANS,
    current: subscription?.status === "active" || subscription?.status === "trialing" ? subscription.planId : null,
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
