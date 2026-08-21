import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listPosts, savePost } from "@/lib/content/store";
import { channelReadiness } from "@/lib/content/publishers";
import { CHANNELS, type Channel, type Post } from "@/lib/content/types";

function workspaceOf(session: Awaited<ReturnType<typeof getSession>>) {
  return session?.companyId ?? "preview";
}

export async function GET() {
  const session = await getSession();
  return NextResponse.json({
    posts: await listPosts(workspaceOf(session)),
    readiness: await channelReadiness(workspaceOf(session)),
  });
}

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) {
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
    companyId: workspaceOf(session),
    channel: body.channel as Channel,
    body: body.body.trim(),
    mediaUrl: body.mediaUrl?.trim() || undefined,
    scheduledAt: scheduledAt.toISOString(),
    status: "scheduled",
    createdAt: new Date().toISOString(),
  };

  return NextResponse.json({ post: await savePost(post) }, { status: 201 });
}
