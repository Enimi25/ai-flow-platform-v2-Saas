import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listPosts, savePost } from "@/lib/content/store";
import { channelReadiness } from "@/lib/content/publishers";
import { CHANNELS, type Channel, type Post } from "@/lib/content/types";

/** Null when nobody is signed in: the queue holds a company's own drafts, so
 *  falling back to a shared workspace would hand them to anyone who asked. */
function workspaceOf(session: Awaited<ReturnType<typeof getSession>>) {
  return session?.companyId ?? null;
}

export async function GET() {
  const session = await getSession();
  const companyId = workspaceOf(session);
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  return NextResponse.json({
    posts: await listPosts(companyId),
    readiness: await channelReadiness(companyId),
  });
}

export async function POST(request: Request) {
  const session = await getSession();
  const companyId = workspaceOf(session);
  if (!companyId) {
    return NextResponse.json({ error: "Sign in to queue a post." }, { status: 401 });
  }

  const body = (await request.json().catch(() => null)) as Partial<Post> | null;
  if (!body?.body?.trim()) {
    return NextResponse.json({ error: "The post needs text." }, { status: 400 });
  }
  if (!CHANNELS.includes(body.channel as Channel)) {
    return NextResponse.json({ error: "Unknown channel." }, { status: 400 });
  }

  const scheduledAt = body.scheduledAt ? new Date(body.scheduledAt) : new Date();
  if (Number.isNaN(scheduledAt.getTime())) {
    return NextResponse.json({ error: "That schedule is not a valid date." }, { status: 400 });
  }

  const post: Post = {
    id: crypto.randomUUID(),
    companyId,
    channel: body.channel as Channel,
    body: body.body.trim(),
    mediaUrl: body.mediaUrl?.trim() || undefined,
    scheduledAt: scheduledAt.toISOString(),
    status: "scheduled",
    createdAt: new Date().toISOString(),
  };

  return NextResponse.json({ post: await savePost(post) }, { status: 201 });
}
