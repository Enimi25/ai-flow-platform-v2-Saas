import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import ffmpegPath from "ffmpeg-static";
import { dataFile } from "@/lib/data-dir";

/**
 * Turns a reel script into an actual vertical MP4.
 *
 * The model has always written shot lists; nothing ever turned them into a
 * file, so "reels on autopilot" ended at a text draft. This renders the text
 * the model wrote as animated cards over the brand image (or a brand colour),
 * which is a publishable reel Meta will accept - not cinema, but honest,
 * automatic and unlimited.
 *
 * Everything is text files + one ffmpeg run. drawtext reads each card from a
 * file rather than the command line, which sidesteps the escaping rules that
 * break on apostrophes, colons and Cyrillic.
 */

const FONT = path.join(process.cwd(), "assets", "fonts", "Inter-SemiBold.ttf");
const W = 1080;
const H = 1920;

export const MEDIA_DIR = () => dataFile("media");

export type ReelInput = {
  /** Post id; names the output file. */
  id: string;
  /** Text cards, in order. Usually the script lines the model wrote. */
  cards: string[];
  /** Shown small at the bottom the whole way through. */
  brand?: string;
  /** Absolute path to a background image; brand colour is used without one. */
  imagePath?: string;
};

/** Wrap to ~14 characters a line - drawtext does not wrap on its own. */
function wrap(text: string, width = 14): string {
  const words = text.replace(/\s+/g, " ").trim().split(" ");
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    if ((line + " " + word).trim().length > width && line) {
      lines.push(line);
      line = word;
    } else {
      line = (line + " " + word).trim();
    }
  }
  if (line) lines.push(line);
  return lines.slice(0, 6).join("\n");
}

function run(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const bin = ffmpegPath as unknown as string;
    if (!bin) return reject(new Error("ffmpeg-static did not resolve a binary for this platform."));
    const child = spawn(bin, args, { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    child.stderr.on("data", (chunk) => {
      err += chunk;
      if (err.length > 20000) err = err.slice(-10000);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error("ffmpeg exited " + code + ": " + err.slice(-400)));
    });
  });
}

/**
 * Renders the reel and returns the public path it will be served from.
 * The caller turns that into an absolute URL with the site origin.
 */
export async function renderReelVideo(input: ReelInput): Promise<{ file: string; publicPath: string }> {
  const cards = input.cards.map((card) => card.trim()).filter(Boolean).slice(0, 6);
  if (!cards.length) throw new Error("A reel needs at least one line of script.");

  const perCard = Math.min(4, Math.max(2.4, 15 / cards.length));
  const total = +(perCard * cards.length).toFixed(2);

  const safeId = input.id.replace(/[^a-z0-9-]/gi, "").slice(0, 40) || crypto.randomUUID();
  const outDir = MEDIA_DIR();
  await fs.mkdir(outDir, { recursive: true });
  const outFile = path.join(outDir, safeId + ".mp4");

  // card texts go through files, never through the filter string
  const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "reel-"));
  const textFiles: string[] = [];
  for (const [index, card] of cards.entries()) {
    const file = path.join(tmp, "card" + index + ".txt");
    await fs.writeFile(file, wrap(card), "utf8");
    textFiles.push(file);
  }
  let brandFile: string | null = null;
  if (input.brand) {
    brandFile = path.join(tmp, "brand.txt");
    await fs.writeFile(brandFile, input.brand.slice(0, 40), "utf8");
  }

  const filters: string[] = [];
  // dark veil so white text reads on any background
  filters.push("drawbox=x=0:y=0:w=" + W + ":h=" + H + ":color=black@0.45:t=fill");
  for (const [index, file] of textFiles.entries()) {
    const from = (index * perCard).toFixed(2);
    const to = ((index + 1) * perCard).toFixed(2);
    filters.push(
      "drawtext=fontfile=" + FONT +
        ":textfile=" + file +
        ":fontcolor=white:fontsize=72:line_spacing=20" +
        ":x=(w-text_w)/2:y=(h-text_h)/2" +
        ":enable='between(t," + from + "," + to + ")'",
    );
  }
  if (brandFile) {
    filters.push(
      "drawtext=fontfile=" + FONT +
        ":textfile=" + brandFile +
        ":fontcolor=white@0.7:fontsize=40" +
        ":x=(w-text_w)/2:y=h-180",
    );
  }

  const args: string[] = ["-y", "-hide_banner", "-loglevel", "error"];
  if (input.imagePath) {
    args.push("-loop", "1", "-t", String(total), "-i", input.imagePath);
    filters.unshift(
      "scale=" + W + ":" + H + ":force_original_aspect_ratio=increase," +
        "crop=" + W + ":" + H + ",setsar=1",
    );
  } else {
    args.push("-f", "lavfi", "-i", "color=c=0x1B2848:s=" + W + "x" + H + ":d=" + total);
  }
  // silent stereo track: players and the Graph API both prefer an audio stream
  args.push("-f", "lavfi", "-t", String(total), "-i", "anullsrc=r=44100:cl=stereo");
  args.push(
    "-filter_complex", "[0:v]" + filters.join(",") + "[v]",
    "-map", "[v]", "-map", "1:a",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
    "-pix_fmt", "yuv420p", "-r", "30",
    "-c:a", "aac", "-b:a", "96k", "-shortest",
    "-movflags", "+faststart",
    outFile,
  );

  try {
    await run(args);
  } finally {
    await fs.rm(tmp, { recursive: true, force: true }).catch(() => undefined);
  }

  const stat = await fs.stat(outFile);
  if (stat.size < 20_000) throw new Error("The rendered reel came out suspiciously small.");
  return { file: outFile, publicPath: "/api/media/" + safeId + ".mp4" };
}

/**
 * The brand image, fetched once and kept next to the videos. Meta pulls the
 * final video over HTTPS, but ffmpeg reading a remote URL mid-render is a
 * flake we do not need.
 */
export async function localBrandImage(): Promise<string | undefined> {
  const url = process.env.CONTENT_DEFAULT_IMAGE_URL;
  if (!url) return undefined;
  const outDir = MEDIA_DIR();
  await fs.mkdir(outDir, { recursive: true });
  const marker = crypto.createHash("sha256").update(url).digest("hex").slice(0, 16);
  const file = path.join(outDir, "brand-" + marker + ".img");
  try {
    await fs.access(file);
    return file;
  } catch {
    /* not cached yet */
  }
  try {
    const response = await fetch(url);
    if (!response.ok) return undefined;
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length < 1000) return undefined;
    await fs.writeFile(file, buffer);
    return file;
  } catch {
    return undefined;
  }
}

/** Absolute origin the served media is reachable at from outside. */
export function siteOrigin(fallback?: string): string {
  const configured = process.env.PUBLIC_SITE_URL;
  if (configured) return configured.replace(/\/$/, "");
  return (fallback ?? "").replace(/\/$/, "");
}
