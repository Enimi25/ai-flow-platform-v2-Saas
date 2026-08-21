import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listLeads } from "@/lib/leads/store";
import { listPosts } from "@/lib/content/store";
import { listBookings } from "@/lib/booking/store";
import { listEvents } from "@/lib/activity";
import { connectionsFor } from "@/lib/content/connections";
import { isGoogleReady } from "@/lib/google/oauth";
import { isStripeReady } from "@/lib/booking/stripe";
import { isEmailReady } from "@/lib/email/send";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const [leads, posts, bookings, events, connections] = await Promise.all([
    listLeads(companyId),
    listPosts(companyId),
    listBookings(companyId),
    listEvents(companyId, 6),
    connectionsFor(companyId),
  ]);

  const now = new Date();
  const upcoming = bookings
    .filter((booking) => booking.status === "paid" && new Date(booking.startsAt) > now)
    .slice(0, 5);

  const steps = [
    { id: "signin", label: "Sign in", done: Boolean(session), href: "/login" },
    { id: "calendar", label: "Connect Google and a calendar", done: isGoogleReady(), href: "/calendar/confirm" },
    { id: "widget", label: "Put the widget on your site", done: false, href: "/install" },
    { id: "channel", label: "Connect a social channel", done: connections.some((c) => c.connected), href: "/social-accounts" },
    { id: "payments", label: "Turn on payments", done: isStripeReady(), href: "/settings" },
    { id: "email", label: "Turn on email", done: isEmailReady(), href: "/settings" },
  ];

  return NextResponse.json({
    totals: {
      leads: leads.length,
      newLeads: leads.filter((lead) => lead.status === "new").length,
      queued: posts.filter((post) => post.status === "scheduled").length,
      published: posts.filter((post) => post.status === "published").length,
      upcoming: upcoming.length,
    },
    recentLeads: leads.slice(0, 5),
    upcoming,
    events,
    steps,
    progress: Math.round((steps.filter((step) => step.done).length / steps.length) * 100),
  });
}
