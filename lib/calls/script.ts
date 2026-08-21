import { ask, tidyText, UNSURE } from "@/lib/model";
import { getSettings } from "@/lib/settings/store";
import { recentTurns } from "@/lib/conversations/store";
import type { CallScript } from "./types";

/**
 * What to say to this one person.
 *
 * The value here does not need a phone line at all: whoever picks up the
 * handset already knows what the customer asked the agent, what was answered,
 * and where the conversation stopped. A generic script sheet does not do that,
 * and neither does a lead row with a phone number on it.
 */
export async function writeScript(input: {
  companyId: string;
  name: string;
  reason: string;
  visitorId?: string;
}): Promise<CallScript | null> {
  const settings = await getSettings(input.companyId);

  const history = input.visitorId
    ? await recentTurns(input.companyId, input.visitorId, 12).catch(() => [])
    : [];

  const conversation = history.length
    ? history.map((turn) => `${turn.role === "agent" ? "Assistant" : "Customer"}: ${turn.text}`).join("\n")
    : "There is no earlier conversation. This is a first contact.";

  const system = [
    `You brief a person about to phone a customer of ${settings.companyName || "this business"}.`,
    settings.businessDescription ? `The business:\n${settings.businessDescription}` : "",
    "",
    "Write the brief as JSON and nothing else, in this exact shape:",
    '{"opening":"...","points":["...","..."],"objections":[{"heard":"...","answer":"..."}],"closing":"..."}',
    "",
    "opening: one or two sentences to say when they pick up. Warm, no script voice.",
    "points: two to four things to cover, drawn from what this person actually asked.",
    "objections: two or three things this specific person is likely to push back on, with a straight answer each.",
    "closing: how to ask for the appointment.",
    "",
    "Never invent a price, a discount or a promise that is not in the business description.",
    "Write in the language the customer used. No em dashes.",
  ]
    .filter(Boolean)
    .join("\n");

  const user = [
    `Who: ${input.name || "a customer"}`,
    `Why we are calling: ${input.reason}`,
    "",
    "What they said to the assistant:",
    conversation,
  ].join("\n");

  const answer = await ask({ system, user, temperature: 0.5, maxTokens: 900, weight: "heavy" });
  if (answer.unsure) return null;

  const text = tidyText(answer.text.replaceAll(UNSURE, "")).trim();
  // models wrap JSON in prose or a fence more often than not
  const body = text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1);
  if (!body) return null;

  try {
    const parsed = JSON.parse(body) as Partial<CallScript>;
    return {
      opening: String(parsed.opening ?? "").slice(0, 400),
      points: (Array.isArray(parsed.points) ? parsed.points : []).slice(0, 5).map((p) => String(p).slice(0, 240)),
      objections: (Array.isArray(parsed.objections) ? parsed.objections : [])
        .slice(0, 4)
        .map((item) => ({
          heard: String((item as { heard?: unknown }).heard ?? "").slice(0, 200),
          answer: String((item as { answer?: unknown }).answer ?? "").slice(0, 400),
        }))
        .filter((item) => item.heard && item.answer),
      closing: String(parsed.closing ?? "").slice(0, 400),
      generatedAt: new Date().toISOString(),
    };
  } catch {
    return null;
  }
}
