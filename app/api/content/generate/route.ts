import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { generatePosts, GeneratorNotConfigured, isGeneratorReady } from "@/lib/content/generate";
import { writeOffline } from "@/lib/content/offline";
import { savePost, listPosts } from "@/lib/content/store";
import { CHANNELS, type Channel, type Post } from "@/lib/content/types";
import { safeRecord } from "@/lib/activity";

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in to generate posts." }, { status: 401 });

  const companyId = session.companyId ?? "preview";
  const body = (await request.json().catch(() => ({}))) as { channel?: Channel; count?: number; everyDays?: number; format?: "post" | "reel" };

  if (!CHANNELS.includes(body.channel as Channel)) {
    return NextResponse.json({ error: "Unknown channel." }, { status: 400 });
  }
  const count = Math.min(Math.max(Number(body.count ?? 5), 1), 10);
  const everyDays = Math.min(Math.max(Number(body.everyDays ?? 2), 1), 14);

  const format = body.format === "reel" ? "reel" : "post";

  try {
    // The model writes when it can. Without a key the workspace still gets
    // usable drafts instead of an error and an empty queue.
    const existing = (await listPosts(companyId)).length;
    const drafts = isGeneratorReady()
      ? await generatePosts({ companyId, channel: body.channel as Channel, count, format })
      : await writeOffline({ companyId, channel: body.channel as Channel, count, format, offset: existing });
    const wroteOffline = !isGeneratorReady();

    const now = Date.now();
    const saved: Post[] = [];
    for (const [index, draft] of drafts.entries()) {
      saved.push(
        await savePost({
          id: crypto.randomUUID(),
          companyId,
          channel: draft.channel,
          body: draft.script?.length
            ? `${draft.body}\n\n--- shot list ---\n${draft.script.map((shot, n) => `${n + 1}. ${shot}`).join("\n")}`
            : draft.body,
          scheduledAt: new Date(now + (index * everyDays + 1) * 86_400_000).toISOString(),
          status: "draft",
          createdAt: new Date().toISOString(),
        }),
      );
    }

    safeRecord({
      companyId,
      kind: "content.generated",
      level: "success",
      title: `${saved.length} ${body.channel} ${format === "reel" ? "reels" : "posts"} written`,
      detail: wroteOffline ? "Written from the built in library, no model key set" : "Written by the model",
    });

    return NextResponse.json({ posts: saved, model: !wroteOffline }, { status: 201 });
  } catch (error) {
    if (error instanceof GeneratorNotConfigured) {
      return NextResponse.json({ error: error.message, missing: error.missing }, { status: 503 });
    }
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Generation failed." },
      { status: 502 },
    );
  }
}
