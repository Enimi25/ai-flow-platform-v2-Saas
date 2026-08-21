import { getSettings } from "@/lib/settings/store";
import { ask, weigh, tidyText, ESCALATION_RULE, UNSURE } from "@/lib/model";
import { appendTurn } from "@/lib/conversations/store";
import { captureLead, detectContact, type Source } from "@/lib/leads/store";
import { safeRecord } from "@/lib/activity";

/**
 * The same brain that answers on the website, answering a direct message.
 *
 * One path means a customer gets the same tone and the same refusal to invent
 * a price whether they wrote on the site, in Messenger or in Instagram.
 */
export async function answerMessage(input: {
  companyId: string;
  from: string;
  text: string;
  source: Source;
}) {
  const { companyId, from, text, source } = input;
  const now = new Date().toISOString();

  await appendTurn({
    companyId,
    visitorId: from,
    source,
    turn: { role: "customer", text, at: now },
  }).catch(() => {});

  const contact = detectContact(text);
  if (contact.found) {
    await captureLead({
      companyId,
      email: contact.email || undefined,
      phone: contact.phone || undefined,
      message: text,
      source,
    }).catch(() => {});
  }

  const settings = await getSettings(companyId);

  const system = [
    `You are ${settings.assistantName || "the assistant"} replying to a direct message for ${settings.companyName || "this business"}.`,
    settings.businessDescription
      ? `What the business does:\n${settings.businessDescription}`
      : "You have no description of the business, so say plainly when you do not know something.",
    "",
    `Tone: ${settings.tone}. This is a chat, so keep it to a few short lines.`,
    "Answer only from the information above. Never invent a price, an address or an opening hour.",
    ESCALATION_RULE,
    `Your goal: ${settings.goal}.`,
    contact.found
      ? "They just gave their contact details. Confirm you have them and say what happens next."
      : `When it fits, ask: ${settings.leadQuestion}`,
    "Never ask for a password or card details. Reply in the language they wrote in.",
  ].join("\n");

  const answer = await ask({
    system,
    user: text,
    temperature: 0.4,
    maxTokens: 400,
    weight: weigh(text),
  });

  const reply = answer.unsure
    ? settings.leadQuestion || "What is the best way to reach you?"
    : tidyText(answer.text.replaceAll(UNSURE, "")).slice(0, 900);

  await appendTurn({
    companyId,
    visitorId: from,
    source,
    turn: { role: "agent", text: reply, at: new Date().toISOString() },
  }).catch(() => {});

  safeRecord({
    companyId,
    kind: `message.${source}`,
    level: "success",
    title: `Replied on ${source}`,
    detail: text.slice(0, 120),
  });

  return reply;
}
