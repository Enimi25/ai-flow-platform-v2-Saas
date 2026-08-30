import { promises as fs } from "node:fs";
import { getSettings } from "@/lib/settings/store";
import { connectionsFor } from "./connections";
import { listPosts, savePost } from "./store";
import { generatePosts, isGeneratorReady } from "./generate";
import { renderReelVideo, localBrandImage, siteOrigin } from "@/lib/content/video";
import { CHANNELS, type Channel, type Post } from "./types";
import { safeRecord } from "@/lib/activity";
import { instantFor } from "@/lib/booking/slots";
import { dataFile } from "@/lib/data-dir";

/**
 * Keeps every workspace's queue full.
 *
 * The factory could already publish, and the scheduler already ran, but nothing
 * ever put a post in the queue: generation sat behind a button. So the machine
 * turned over publishing an empty list.
 *
 * Only channels a business has actually connected are topped up. Generating for
 * a channel with no token just fills the queue with posts that will fail at
 * midnight and wake somebody up for nothing.
 */

const WORKSPACES = dataFile("workspaces.json");
const HOURS = [10, 14];
const REEL_HOUR = [18];
const EVERY = 6 * 60 * 60 * 1000;

/** TikTok needs a video, so a text-only autopilot cannot feed it. */
const TEXT_CHANNELS: Channel[] = ["facebook", "instagram"];

/**
 * Instagram refuses a post without media, so an autopilot caption alone would
 * be queued only to fail at publish time. With a brand image configured the
 * caption rides on that; without one, Instagram is left out of the top-up.
 */
const DEFAULT_IMAGE = process.env.CONTENT_DEFAULT_IMAGE_URL ?? "";

let lastRun = 0;

async function allCompanyIds() {
  try {
    const raw = JSON.parse(await fs.readFile(WORKSPACES, "utf8")) as Record<string, { companyId: string }>;
    return Object.values(raw).map((workspace) => workspace.companyId);
  } catch {
    return [];
  }
}

/**
 * The next few posting moments after the last one already queued.
 *
 * In the business's own timezone: setHours() would use the server's, and a
 * clinic in Moscow would have found its lunchtime posts going out at seven in
 * the morning.
 */
function slotsAfter(from: Date, count: number, zone: string, hours: number[] = HOURS) {
  const out: string[] = [];
  const day = new Date(from);

  for (let ahead = 0; ahead < 30 && out.length < count; ahead += 1) {
    const cursor = new Date(day.getTime() + ahead * 86_400_000);
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(cursor);
    const get = (type: string) => Number(parts.find((part) => part.type === type)?.value ?? 0);

    for (const hour of hours) {
      if (out.length >= count) break;
      const at = instantFor(get("year"), get("month"), get("day"), hour, 0, zone);
      if (at > from) out.push(at.toISOString());
    }
  }
  return out;
}

async function topUp(companyId: string) {
  const settings = await getSettings(companyId);
  if (!settings.contentAuto) return 0;
  if (!settings.businessDescription) return 0;

  const links: Links = await connectionsFor(companyId).catch(() => []);
  // connectionsFor lists every channel with a flag, so the flag is what counts
  const connected = CHANNELS.filter(
    (channel) =>
      TEXT_CHANNELS.includes(channel) &&
      (channel !== "instagram" || DEFAULT_IMAGE) &&
      links.some((link) => link.channel === channel && link.connected),
  );
  // no early return: a workspace with only TikTok still gets its reels

  const posts = await listPosts(companyId);
  const now = new Date();
  let made = 0;

  for (const channel of connected) {
    const pending = posts.filter(
      (post) => post.channel === channel && post.status === "scheduled" && new Date(post.scheduledAt) > now,
    );
    const want = Math.max(0, settings.contentPerWeek - pending.length);
    if (!want) continue;

    const last = pending
      .map((post) => new Date(post.scheduledAt))
      .sort((a, b) => b.getTime() - a.getTime())[0];

    const drafts = await generatePosts({ companyId, channel, count: want }).catch(() => []);
    const when = slotsAfter(last && last > now ? last : now, drafts.length, settings.timezone || "Europe/London");

    for (const [index, draft] of drafts.entries()) {
      const post: Post = {
        id: crypto.randomUUID(),
        companyId,
        channel,
        body: draft.body,
        mediaUrl: channel === "instagram" ? DEFAULT_IMAGE : undefined,
        scheduledAt: when[index],
        status: "scheduled",
        createdAt: new Date().toISOString(),
      };
      await savePost(post);
      made += 1;
    }
  }

  made += await topUpReels(companyId, settings, links, posts, now);

  if (made) {
    safeRecord({
      companyId,
      kind: "content.queued",
      level: "success",
      title: `Queued ${made} post${made === 1 ? "" : "s"}`,
      detail: "The content factory topped the schedule up on its own.",
    });
  }

  return made;
}

/** One reel a day per connected channel, rendered to a real video at 18:00. */
const REEL_CHANNELS: Channel[] = ["instagram", "facebook", "tiktok"];
const REELS_AHEAD = 3;

type Links = Awaited<ReturnType<typeof connectionsFor>>;
type Settings = Awaited<ReturnType<typeof getSettings>>;

async function topUpReels(companyId: string, settings: Settings, links: Links, posts: Post[], now: Date) {
  // Meta pulls the finished file over HTTPS, so without a public origin a
  // rendered reel would be a video nobody can fetch.
  const origin = siteOrigin();
  if (!origin) return 0;

  const connected = REEL_CHANNELS.filter((channel) =>
    links.some((link) => link.channel === channel && link.connected),
  );
  if (!connected.length) return 0;

  const brandImage = await localBrandImage();
  let made = 0;

  for (const channel of connected) {
    const pending = posts.filter(
      (post) =>
        post.channel === channel &&
        post.status === "scheduled" &&
        Boolean(post.mediaUrl?.includes("/api/media/")) &&
        new Date(post.scheduledAt) > now,
    );
    const want = Math.max(0, REELS_AHEAD - pending.length);
    if (!want) continue;

    const drafts = await generatePosts({ companyId, channel, count: want, format: "reel" }).catch(() => []);
    const last = pending
      .map((post) => new Date(post.scheduledAt))
      .sort((a, b) => b.getTime() - a.getTime())[0];
    const when = slotsAfter(last && last > now ? last : now, drafts.length, settings.timezone || "Europe/London", REEL_HOUR);

    for (const [index, draft] of drafts.entries()) {
      if (!draft.script?.length) continue;
      const id = crypto.randomUUID();
      try {
        const video = await renderReelVideo({
          id,
          cards: draft.script,
          brand: settings.companyName || undefined,
          imagePath: brandImage,
        });
        await savePost({
          id,
          companyId,
          channel,
          body: draft.body,
          mediaUrl: origin + video.publicPath,
          scheduledAt: when[index],
          status: "scheduled",
          createdAt: new Date().toISOString(),
        });
        made += 1;
      } catch (error) {
        console.error("[autopilot] reel render failed:", error instanceof Error ? error.message : error);
      }
    }
  }

  return made;
}

/** Called by the scheduler. Cheap to call often; it works every six hours. */
export async function runAutopilot(now = Date.now()) {
  if (!isGeneratorReady()) return { skipped: "no model" as const, queued: 0 };
  if (now - lastRun < EVERY) return { skipped: "too soon" as const, queued: 0 };
  lastRun = now;

  let queued = 0;
  for (const companyId of await allCompanyIds()) {
    queued += await topUp(companyId).catch(() => 0);
  }
  return { skipped: null, queued };
}
