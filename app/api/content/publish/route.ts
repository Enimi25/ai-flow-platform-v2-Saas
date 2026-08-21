import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { publishNow } from "@/lib/content/runner";

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Sign in to publish." }, { status: 401 });
  }

  const { id } = (await request.json().catch(() => ({}))) as { id?: string };
  if (!id) return NextResponse.json({ error: "Which post?" }, { status: 400 });

  const post = await publishNow(id);
  if (!post) return NextResponse.json({ error: "That post is gone." }, { status: 404 });
  if (post.companyId !== (session.companyId ?? "preview")) {
    return NextResponse.json({ error: "That post belongs to another workspace." }, { status: 403 });
  }

  return NextResponse.json({ post }, { status: post.status === "failed" ? 502 : 200 });
}
