import type { Channel, Post } from "./types";
import { REQUIRES_MEDIA } from "./types";
import { connectionFor } from "./connections";

const GRAPH = "https://graph.facebook.com/v21.0";

export class NotConfigured extends Error {
  constructor(public readonly missing: string[]) {
    super(`Missing credentials: ${missing.join(", ")}`);
    this.name = "NotConfigured";
  }
}

async function graph(url: string, body: Record<string, string>) {
  const response = await fetch(url, {
    method: "POST",
    body: new URLSearchParams(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? `Request failed with ${response.status}`);
  }
  return payload as { id?: string };
}

/** A Page post. Text alone is allowed, a photo goes to the photos edge. */
async function publishFacebook(post: Post) {
  const link = await connectionFor(post.companyId, "facebook");
  if (!link) throw new NotConfigured(["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"]);
  const pageId = link.accountId;
  const token = link.accessToken;
  const result = post.mediaUrl
    ? await graph(`${GRAPH}/${pageId}/photos`, {
        url: post.mediaUrl,
        caption: post.body,
        access_token: token,
      })
    : await graph(`${GRAPH}/${pageId}/feed`, {
        message: post.body,
        access_token: token,
      });
  if (!result.id) throw new Error("Facebook accepted the call but returned no post id.");
  return result.id;
}

/** Instagram publishes in two steps: build a container, then release it. */
async function publishInstagram(post: Post) {
  const link = await connectionFor(post.companyId, "instagram");
  if (!link) throw new NotConfigured(["INSTAGRAM_USER_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"]);
  const userId = link.accountId;
  const token = link.accessToken;
  if (!post.mediaUrl) throw new Error("Instagram will not accept a post without an image or video.");

  const container = await graph(`${GRAPH}/${userId}/media`, {
    image_url: post.mediaUrl,
    caption: post.body,
    access_token: token,
  });
  if (!container.id) throw new Error("Instagram did not return a media container.");

  const published = await graph(`${GRAPH}/${userId}/media_publish`, {
    creation_id: container.id,
    access_token: token,
  });
  if (!published.id) throw new Error("Instagram did not return a published media id.");
  return published.id;
}

/** Direct post. The app must pass TikTok audit before it can post publicly. */
async function publishTikTok(post: Post) {
  const link = await connectionFor(post.companyId, "tiktok");
  if (!link) throw new NotConfigured(["TIKTOK_ACCESS_TOKEN"]);
  const token = link.accessToken;
  if (!post.mediaUrl) throw new Error("TikTok will not accept a post without a video.");

  const response = await fetch("https://open.tiktokapis.com/v2/post/publish/video/init/", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json; charset=UTF-8",
    },
    body: JSON.stringify({
      post_info: { title: post.body.slice(0, 150), privacy_level: "SELF_ONLY" },
      source_info: { source: "PULL_FROM_URL", video_url: post.mediaUrl },
    }),
  });
  const payload = await response.json();
  if (!response.ok || payload?.error?.code !== "ok") {
    throw new Error(payload?.error?.message ?? `TikTok rejected the post (${response.status}).`);
  }
  return payload.data?.publish_id ?? "pending";
}

const PUBLISHERS: Record<Channel, (post: Post) => Promise<string>> = {
  facebook: publishFacebook,
  instagram: publishInstagram,
  tiktok: publishTikTok,
};

export type PublishResult =
  | { ok: true; externalId: string }
  | { ok: false; error: string; missing?: string[] };

export async function publish(post: Post): Promise<PublishResult> {
  if (REQUIRES_MEDIA[post.channel] && !post.mediaUrl) {
    return { ok: false, error: `${post.channel} requires media.` };
  }

  // Dry run walks the whole pipeline without calling a network. It exists so the
  // schedule can be watched working before any account is connected.
  if (process.env.CONTENT_DRY_RUN === "1") {
    console.log(`[dry-run] would post to ${post.channel}: ${post.body.slice(0, 70).replace(/\n/g, " ")}…`);
    return { ok: true, externalId: `dry-run-${post.id.slice(0, 8)}` };
  }
  try {
    return { ok: true, externalId: await PUBLISHERS[post.channel](post) };
  } catch (error) {
    if (error instanceof NotConfigured) {
      return { ok: false, error: error.message, missing: error.missing };
    }
    return { ok: false, error: error instanceof Error ? error.message : "Unknown failure." };
  }
}

/** What the Content screen shows for a given workspace. */
export async function channelReadiness(
  companyId = "preview",
): Promise<Record<Channel, { ready: boolean; missing: string[]; own: boolean }>> {
  const entries = await Promise.all(
    (["facebook", "instagram", "tiktok"] as Channel[]).map(async (channel) => {
      const link = await connectionFor(companyId, channel);
      const missing: Record<Channel, string[]> = {
        facebook: ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"],
        instagram: ["INSTAGRAM_USER_ID", "FACEBOOK_PAGE_ACCESS_TOKEN"],
        tiktok: ["TIKTOK_ACCESS_TOKEN"],
      };
      return [
        channel,
        { ready: Boolean(link), missing: link ? [] : missing[channel], own: Boolean(link?.own) },
      ] as const;
    }),
  );
  return Object.fromEntries(entries) as Record<Channel, { ready: boolean; missing: string[]; own: boolean }>;
}
