import { getSettings } from "@/lib/settings/store";
import { ask, tidyText, NoModelAvailable } from "@/lib/model";
import { CHANNEL_LABEL, type Channel } from "./types";

const GROQ = "https://api.groq.com/openai/v1/chat/completions";
// Groq has retired every Llama model. Asking for one is exactly what leaves the
// production chat answering "AI connection error" on every message.
const MODEL = process.env.GROQ_MODEL || "openai/gpt-oss-120b";

export class GeneratorNotConfigured extends Error {
  constructor(public readonly missing: string[]) {
    super(`Post generation is not connected. Missing: ${missing.join(", ")}`);
    this.name = "GeneratorNotConfigured";
  }
}

export function isGeneratorReady() {
  // the ladder in lib/model tries Groq first and this machine's Ollama second
  return Boolean(process.env.GROQ_API_KEY) || Boolean(process.env.OLLAMA_URL) || true;
}

/** A reel is a shot list plus a caption. A post is just the caption. */
const REEL_SHAPE: Record<Channel, string> = {
  facebook:
    "A Facebook reel of 15 to 20 seconds. Four to six shots. Each shot: seconds, what is on screen, and the on screen text.",
  instagram:
    "An Instagram reel of 12 to 18 seconds. Four to six shots, vertical. Each shot: seconds, what is on screen, and the on screen text. Hook in the first two seconds.",
  tiktok:
    "A TikTok video of 15 to 25 seconds. Five to seven shots. Each shot: seconds, what is on screen, and the on screen text. The first shot has to stop the scroll.",
};

/** Each network rewards a different shape, so the brief changes with the channel. */
const SHAPE: Record<Channel, string> = {
  facebook:
    "A short Facebook post. Open with a concrete situation the owner recognises, not a slogan. Three to six short paragraphs. No hashtags.",
  instagram:
    "An Instagram caption. Two to four short lines, then a blank line, then five to seven lowercase hashtags on one line.",
  tiktok:
    "A TikTok caption of one or two sentences, plus three or four lowercase hashtags. Also give a six to twelve second on screen idea in square brackets on the first line.",
};

export type Format = "post" | "reel";
type Generated = { channel: Channel; body: string; script?: string[] };

export async function generatePosts(input: {
  companyId: string;
  channel: Channel;
  count: number;
  format?: Format;
}): Promise<Generated[]> {
  const format: Format = input.format ?? "post";

  const settings = await getSettings(input.companyId);
  const business = [
    settings.companyName && `Business: ${settings.companyName}`,
    settings.industry && `Industry: ${settings.industry}`,
    settings.businessDescription && `What it does: ${settings.businessDescription}`,
    settings.website && `Website: ${settings.website}`,
  ]
    .filter(Boolean)
    .join("\n");

  const system = [
    "You write social posts for a small business. You are not a marketer showing off.",
    "Rules that matter more than style:",
    "- Never invent numbers, prices, discounts, awards or customer quotes. If you have no figure, write none.",
    "- No emoji unless the channel brief asks for them.",
    "- No em dashes, en dashes or non breaking hyphens. A plain hyphen only.",
    "- The shot list must be written in the same language as the caption.",
    "- Write in the language the business description is written in. If there is none, write in English.",
    `- Tone: ${settings.tone}. The point of every post: ${settings.goal}.`,
    format === "reel"
      ? 'Return strictly a JSON array of objects, each {"caption": string, "script": [string, ...]}. No commentary, no markdown fence.'
      : "Return strictly a JSON array of strings. No commentary, no keys, no markdown fence.",
  ].join("\n");

  const user = [
    business || "Business: a small local business that takes enquiries by message.",
    "",
    format === "reel"
      ? `Write ${input.count} different reels for ${CHANNEL_LABEL[input.channel]}. Nothing that needs a budget, an actor or a studio: a phone, a screen and a hand are all that exist.`
      : `Write ${input.count} different posts for ${CHANNEL_LABEL[input.channel]}.`,
    format === "reel" ? REEL_SHAPE[input.channel] : SHAPE[input.channel],
    "Each post must stand on its own and open differently from the others.",
  ].join("\n");

  let answer;
  try {
    answer = await ask({ system, user, temperature: 0.85, maxTokens: 1800, weight: "heavy" });
  } catch (error) {
    if (error instanceof NoModelAvailable) throw new GeneratorNotConfigured(["GROQ_API_KEY or a local Ollama model"]);
    throw error;
  }

  const text = answer.text;
  const parsed = parseAny(text);
  if (!parsed.length) throw new Error("The model returned nothing usable.");

  return parsed.slice(0, input.count).map((entry) =>
    typeof entry === "string"
      ? { channel: input.channel, body: tidy(entry) }
      : {
          channel: input.channel,
          body: tidy(entry.caption),
          script: entry.script.map(tidy),
        },
  );
}

/**
 * Models reach for typographic dashes and non breaking hyphens that look wrong
 * in a caption and break word wrapping on a phone. Cleaned on the way out
 * rather than hoped for in the prompt.
 */
const tidy = tidyText;

type Entry = string | { caption: string; script: string[] };

/** Models wrap JSON in prose or fences often enough that this has to be forgiving. */
function parseAny(text: string): Entry[] {
  const cleaned = text.replace(/```json|```/g, "").trim();
  const usable = (value: unknown): Entry[] => {
    if (!Array.isArray(value)) return [];
    return value.filter((entry): entry is Entry => {
      if (typeof entry === "string") return Boolean(entry.trim());
      return Boolean(
        entry &&
          typeof entry === "object" &&
          typeof (entry as { caption?: unknown }).caption === "string" &&
          Array.isArray((entry as { script?: unknown }).script),
      );
    });
  };

  try {
    const found = usable(JSON.parse(cleaned));
    if (found.length) return found;
  } catch {
    /* fall through */
  }

  const start = cleaned.indexOf("[");
  const end = cleaned.lastIndexOf("]");
  if (start !== -1 && end > start) {
    try {
      return usable(JSON.parse(cleaned.slice(start, end + 1)));
    } catch {
      /* fall through */
    }
  }
  return [];
}
