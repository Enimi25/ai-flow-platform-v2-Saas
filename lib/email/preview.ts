import { ask, tidyText, UNSURE } from "@/lib/model";

/**
 * A sample conversation, written for the business that just asked for a demo.
 *
 * The proposal used to say "here is what your agent would have done" and then
 * show a price list, which is a promise the email did not keep. Given four lines
 * about a business, the same model that would run their agent can answer three
 * of their own customers' questions — and that is the only part of the email
 * anybody will actually read.
 */
export type Exchange = { asked: string; answered: string };

export async function previewConversation(business: string): Promise<Exchange[]> {
  const system = [
    "You are showing a small business owner what an AI agent would say to their customers.",
    "",
    "Write three short exchanges as JSON and nothing else:",
    '[{"asked":"...","answered":"..."},{"asked":"...","answered":"..."},{"asked":"...","answered":"..."}]',
    "",
    "asked: a question this business really gets. Ordinary wording, the way a customer types.",
    "answered: how the agent would reply. Two sentences at most. Warm, direct, no sales voice.",
    "",
    "Use only what the description says. Never invent a price, an address or an opening hour.",
    "If the description gives a price, quote it exactly. If it does not, the answer offers to find out.",
    "One of the three should end by offering an appointment.",
    "Write in the language the description is written in. No em dashes.",
  ].join("\n");

  const answer = await ask({
    system,
    user: `The business, in their own words:\n${business}`,
    temperature: 0.5,
    maxTokens: 800,
    weight: "heavy",
  });
  if (answer.unsure) return [];

  const text = tidyText(answer.text.replaceAll(UNSURE, "")).trim();
  const body = text.slice(text.indexOf("["), text.lastIndexOf("]") + 1);
  if (!body) return [];

  try {
    const parsed = JSON.parse(body) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .slice(0, 3)
      .map((item) => ({
        asked: String((item as { asked?: unknown }).asked ?? "").slice(0, 200),
        answered: String((item as { answered?: unknown }).answered ?? "").slice(0, 400),
      }))
      .filter((item) => item.asked && item.answered);
  } catch {
    return [];
  }
}
