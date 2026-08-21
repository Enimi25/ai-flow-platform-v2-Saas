import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { getPost, savePost, deletePost } from "@/lib/content/store";
import type { PostStatus } from "@/lib/content/types";
import { safeRecord } from "@/lib/activity";

const ALLOWED: PostStatus[] = ["draft", "scheduled"];

/** Approve a draft, or send an approved post back to drafts. */
export async function PATCH(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { id, status, scheduledAt } = (await request.json().catch(() => ({}))) as {
    id?: string;
    status?: PostStatus;
    scheduledAt?: string;
  };
  if (!id || !status || !ALLOWED.includes(status)) {
    return NextResponse.json({ error: "Need an id and a valid status." }, { status: 400 });
  }

  const post = await getPost(id);
  if (!post) return NextResponse.json({ error: "No such post." }, { status: 404 });
  if (post.companyId !== (session.companyId ?? "preview")) {
    return NextResponse.json({ error: "That post belongs to another workspace." }, { status: 403 });
  }

  const next = await savePost({
    ...post,
    status,
    scheduledAt: scheduledAt ?? post.scheduledAt,
    error: undefined,
  });

  if (status === "scheduled") {
    safeRecord({
      companyId: next.companyId,
      kind: "content.approved",
      level: "info",
      title: `${next.channel} post approved`,
      detail: new Date(next.scheduledAt).toLocaleString(),
    });
  }

  return NextResponse.json({ post: next });
}

export async function DELETE(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { id } = (await request.json().catch(() => ({}))) as { id?: string };
  if (!id) return NextResponse.json({ error: "Need an id." }, { status: 400 });

  const post = await getPost(id);
  if (!post) return NextResponse.json({ error: "No such post." }, { status: 404 });
  if (post.companyId !== (session.companyId ?? "preview")) {
    return NextResponse.json({ error: "That post belongs to another workspace." }, { status: 403 });
  }

  await deletePost(id);
  return NextResponse.json({ ok: true });
}
