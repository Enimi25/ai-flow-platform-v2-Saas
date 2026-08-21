import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listLeads } from "@/lib/leads/store";
import { listPosts } from "@/lib/content/store";
import { listBookings } from "@/lib/booking/store";

function bucketByDay(items: { createdAt: string }[], days = 14) {
  const today = new Date();
  const out: { day: string; count: number }[] = [];
  for (let back = days - 1; back >= 0; back -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - back);
    const key = date.toISOString().slice(0, 10);
    out.push({ day: key, count: items.filter((item) => item.createdAt.slice(0, 10) === key).length });
  }
  return out;
}

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const [leads, posts, bookings] = await Promise.all([
    listLeads(companyId),
    listPosts(companyId),
    listBookings(companyId),
  ]);

  const converted = leads.filter((lead) => lead.status === "converted").length;
  const paid = bookings.filter((booking) => booking.status === "paid");
  const revenueCents = paid.reduce((total, booking) => total + booking.amountCents, 0);

  const count = <T extends string>(items: { [k: string]: unknown }[], key: string) =>
    items.reduce<Record<string, number>>((totals, item) => {
      const value = String(item[key]);
      totals[value] = (totals[value] ?? 0) + 1;
      return totals;
    }, {}) as Record<T, number>;

  return NextResponse.json({
    totals: {
      leads: leads.length,
      converted,
      conversionRate: leads.length ? Math.round((converted / leads.length) * 1000) / 10 : 0,
      published: posts.filter((post) => post.status === "published").length,
      queued: posts.filter((post) => post.status === "scheduled").length,
      bookings: paid.length,
      revenueCents,
      currency: paid[0]?.currency?.toUpperCase() ?? "USD",
    },
    leadsByStatus: count(leads, "status"),
    leadsBySource: count(leads, "source"),
    postsByStatus: count(posts, "status"),
    daily: bucketByDay(leads),
  });
}
