import { NextResponse } from "next/server";
import { captureLead, detectContact } from "@/lib/leads/store";
import { appendTurn } from "@/lib/conversations/store";
import { getSettings } from "@/lib/settings/store";
import { ask, weigh, tidyText, ESCALATION_RULE, UNSURE, NoModelAvailable } from "@/lib/model";
import { safeRecord } from "@/lib/activity";

/** One short line, in the customer's own language, when a person has to take over. */
async function handover(question: string, leadQuestion: string) {
  const fallback = leadQuestion || "What is the best phone number or email to reach you?";
  try {
    const written = await ask({
      system: [
        "Write one short reply to a customer whose question the assistant cannot answer.",
        "Say a colleague will come back to them, then ask for a phone number or an email.",
        "Two sentences at most. Reply in the same language the customer used. No apology, no preamble.",
      ].join("\n"),
      user: question,
      temperature: 0.3,
      maxTokens: 400,
      weight: "light",
    });
    return tidyText(written.text.replaceAll(UNSURE, "")).slice(0, 400) || fallback;
  } catch {
    return fallback;
  }
}

export async function POST(request: Request) {
  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > 4_000) return NextResponse.json({ message: "Message is too large." }, { status: 413 });

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request." }, { status: 400 });
  }

  const payload = body as { message?: unknown; companyId?: unknown; visitorId?: unknown };
  const message = typeof payload?.message === "string" ? payload.message.trim().slice(0, 600) : "";
  const companyId = typeof payload?.companyId === "string" ? payload.companyId.slice(0, 80) : "preview";
  const visitorId = typeof payload?.visitorId === "string" ? payload.visitorId.slice(0, 80) : "anonymous";

  if (message.length < 2) return NextResponse.json({ message: "Enter a question and try again." }, { status: 422 });

  const now = new Date().toISOString();
  await appendTurn({ companyId, visitorId, turn: { role: "customer", text: message, at: now } }).catch(() => {});

  // a visitor who leaves contact details is a lead, whatever the agent answers next
  const contact = detectContact(message);
  if (contact.found) {
    const captured = await captureLead({
      companyId,
      email: contact.email || undefined,
      phone: contact.phone || undefined,
      message,
      source: "website",
    }).catch(() => null);
    if (captured) {
      await appendTurn({
        companyId,
        visitorId,
        turn: { role: "agent", text: "[contact captured]", at: now },
        leadId: captured.lead.id,
      }).catch(() => {});
    }
  }

  const settings = await getSettings(companyId);

  const system = [
    `You are ${settings.assistantName || "the assistant"} answering customers for ${settings.companyName || "this business"}.`,
    settings.businessDescription
      ? `What the business does:\n${settings.businessDescription}`
      : "You have no description of the business, so say plainly when you do not know something.",
    "",
    "How to answer:",
    `- Tone: ${settings.tone}. Short. No preamble, no sales voice.`,
    "- Answer only from what the business description says. Never invent a price, an address, an opening hour or a promise.",
    `- ${ESCALATION_RULE}`,
    `- Your goal in the conversation: ${settings.goal}.`,
    contact.found
      ? "- The customer just gave their contact details. Confirm you have them and say what happens next."
      : `- When it fits naturally, ask: ${settings.leadQuestion}`,
    "- Never ask for a password or card details.",
    "- Reply in the language the customer wrote in.",
  ].join("\n");

  try {
    const answer = await ask({
      system,
      user: message,
      temperature: 0.4,
      maxTokens: 400,
      weight: weigh(message),
    });

    // Nobody could answer from the business description. That is a handover,
    // not a failure, and it is the moment to ask for a way to reach them. The
    // sentence is written rather than templated so it lands in the language the
    // customer actually wrote in.
    const reply = answer.unsure
      ? await handover(message, settings.leadQuestion)
      : tidyText(answer.text.replaceAll(UNSURE, "")).slice(0, 2_000);

    if (answer.unsure) {
      safeRecord({
        companyId,
        kind: "chat.handover",
        level: "warn",
        title: "A question no model could answer",
        detail: message.slice(0, 140),
      });
    }

    // A customer got an answer, but not from the provider that should have given
    // it. Nobody notices in the chat, so it has to show up on the Activity screen.
    const primary = (process.env.MODEL_PROVIDERS || "groq,ollama").split(",")[0]?.trim();
    if (!answer.unsure && primary && answer.via !== primary) {
      safeRecord({
        companyId,
        kind: "chat.fallback",
        level: "warn",
        title: `${primary} did not answer, ${answer.via} covered it`,
        detail: `model ${answer.model}`,
      });
    }
    await appendTurn({
      companyId,
      visitorId,
      turn: { role: "agent", text: reply, at: new Date().toISOString() },
    }).catch(() => {});

    return NextResponse.json({ reply, via: answer.via, weight: answer.weight });
  } catch (error) {
    if (error instanceof NoModelAvailable) {
      safeRecord({
        companyId,
        kind: "chat.no_model",
        level: "error",
        title: "The assistant could not answer a customer",
        detail: error.tried.join(" | ").slice(0, 200),
      });
      return NextResponse.json(
        { message: "I cannot reach my brain right now. Leave an email and a person will come back to you." },
        { status: 503 },
      );
    }
    return NextResponse.json({ message: "The assistant is unavailable right now." }, { status: 502 });
  }
}
