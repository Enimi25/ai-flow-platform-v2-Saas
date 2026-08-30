import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { generatePosts, GeneratorNotConfigured, isGeneratorReady } from "@/lib/content/generate";
import { writeOffline } from "@/lib/content/offline";
import { savePost, listPosts } from "@/lib/content/store";
import { CHANNELS, type Channel, type Post } from "@/lib/content/types";
import { safeRecord } from "@/lib/activity";
import { renderReelVideo, localBrandImage, siteOrigin } from "@/lib/content/video";
import { getSettings } from "@/lib/settings/store";

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in to generate posts." }, { status: 401 });

  const companyId = session.companyId ?? "preview";
  const body = (await request.json().catch(() => ({}))) as { channel?: Channel; count?: number; everyDays?: number; format?: "post" | "reel"; topic?: string };

  if (!CHANNELS.includes(body.channel as Channel)) {
    return NextResponse.json({ error: "Unknown channel." }, { status: 400 });
  }
  const count = Math.min(Math.max(Number(body.count ?? 5), 1), 10);
  const everyDays = Math.min(Math.max(Number(body.everyDays ?? 2), 1), 14);

  const format = body.format === "reel" ? "reel" : "post";
  const topic = typeof body.topic === "string" ? body.topic.trim().slice(0, 600) : "";

  try {
    // The model writes when it can. Without a key the workspace still gets
    // usable drafts instead of an error and an empty queue.
    const existing = (await listPosts(companyId)).length;
    const drafts = isGeneratorReady()
      ? await generatePosts({ companyId, channel: body.channel as Channel, count, format, topic: topic || undefined })
      : await writeOffline({ companyId, channel: body.channel as Channel, count, format, offset: existing });
    const wroteOffline = !isGeneratorReady();

    const now = Date.now();
    const origin = siteOrigin(new URL(request.url).origin);
    const brandImage = format === "reel" ? await localBrandImage() : undefined;
    const settings = format === "reel" ? await getSettings(companyId) : null;

    const saved: Post[] = [];
    let rendered = 0;
    for (const [index, draft] of drafts.entries()) {
      const id = crypto.randomUUID();
      let mediaUrl: string | undefined;
      let body = draft.body;

      if (format === "reel" && draft.script?.length) {
        // The script becomes the video; the caption stays a caption.
        try {
          const video = await renderReelVideo({
            id,
            cards: draft.script,
            brand: settings?.companyName || undefined,
            imagePath: brandImage,
          });
          mediaUrl = origin ? origin + video.publicPath : video.publicPath;
          rendered += 1;
        } catch (error) {
          // No video, no silent loss: the shot list rides along in the draft.
          body = `${draft.body}\n\n--- shot list ---\n${draft.script.map((shot, n) => `${n + 1}. ${shot}`).join("\n")}`;
          console.error("[content] reel render failed:", error instanceof Error ? error.message : error);
        }
      }

      saved.push(
        await savePost({
          id,
          companyId,
          channel: draft.channel,
          body,
          mediaUrl,
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
      detail: wroteOffline
        ? "Written from the built in library, no model key set"
        : format === "reel"
          ? `Written by the model, ${rendered} of ${saved.length} rendered to video`
          : "Written by the model",
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
