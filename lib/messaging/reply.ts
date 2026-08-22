import { getSettings } from "@/lib/settings/store";
import { ask, weigh, tidyText, ESCALATION_RULE, UNSURE } from "@/lib/model";
import { appendTurn } from "@/lib/conversations/store";
import { captureLead, detectContact, type Source } from "@/lib/leads/store";
import { safeRecord } from "@/lib/activity";
import { answerLanguage } from "@/lib/language";
import { freeSlots } from "@/lib/booking/slots";
import { confirmBooking, bookingLine, BOOK_MARK, ANY_MARK } from "@/lib/booking/confirm";
import { recentTurns } from "@/lib/conversations/store";

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

  // The same openings the website agent offers. A customer who writes on
  // Instagram is not a lesser customer, and until now could not book at all.
  const slots = await freeSlots(settings, { limit: 6 }).catch(() => []);
  const history = await recentTurns(companyId, from, 10).catch(() => []);
  const earlier = history.slice(0, -1);

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
    "Never ask for a password or card details.",
    `Write your entire reply in ${answerLanguage(text)}. Not a related language, that one.`,
    ...(slots.length
      ? [
          "",
          "Appointments you can actually offer, and nothing else:",
          ...slots.map((slot, index) => `  ${index + 1}. ${slot.label}  (${slot.startsAt})`),
          "",
          "Offer two or three when they want to book. Never invent a different time.",
          "Once they settle on one and you have a way to reach them, confirm it and finish with",
          "[[BOOK:n]] where n is that appointment's number above. Just the number.",
        ]
      : []),
  ].join("\n");

  const answer = await ask({
    system,
    user: earlier.length
      ? [
          "Conversation so far:",
          ...earlier.map((turn) => `${turn.role === "agent" ? "You" : "Customer"}: ${turn.text}`),
          "",
          `Customer: ${text}`,
        ].join("\n")
      : text,
    temperature: 0.4,
    maxTokens: 400,
    weight: weigh(text),
  });

  const marked = answer.unsure ? null : answer.text.match(BOOK_MARK);
  const chosen = marked ? slots[Number(marked[1]) - 1] : undefined;
  const booked = chosen
    ? await confirmBooking({
        settings,
        startsAt: chosen.startsAt,
        customerEmail: contact.email || undefined,
        customerName: contact.phone || from,
      }).catch(() => null)
    : null;

  let reply = answer.unsure
    ? settings.leadQuestion || "What is the best way to reach you?"
    : tidyText(answer.text.replaceAll(UNSURE, "").replace(ANY_MARK, "")).trim().slice(0, 900);

  if (marked && !booked) {
    reply = `${reply}\n\nThat time has just gone. Shall I look at the next one?`.trim();
  }
  if (booked) {
    reply = `${reply}\n\n✓ ${bookingLine(settings, booked.startsAt)}`.trim();
  }

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
