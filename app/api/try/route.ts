import { NextResponse } from "next/server";
import { presetFor } from "@/lib/demo/presets";
import { ask, weigh, tidyText, ESCALATION_RULE, UNSURE } from "@/lib/model";

/**
 * The try-it panel on the landing page.
 *
 * Deliberately separate from /api/chat: nothing here is stored, no lead is
 * captured, and the business description comes from a fixed table chosen by
 * key. A visitor picks which shop to talk to, not what the assistant believes.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ message: "Invalid request." }, { status: 400 });
  }

  const data = body as { preset?: unknown; message?: unknown; history?: unknown };
  const preset = presetFor(data.preset);
  if (!preset) return NextResponse.json({ message: "Pick a business first." }, { status: 422 });

  const message = typeof data.message === "string" ? data.message.trim().slice(0, 300) : "";
  if (message.length < 2) return NextResponse.json({ message: "Ask something." }, { status: 422 });

  const history = Array.isArray(data.history)
    ? data.history
        .slice(-6)
        .filter(
          (turn): turn is { role: string; text: string } =>
            !!turn && typeof turn === "object" && typeof (turn as { text?: unknown }).text === "string",
        )
        .map((turn) => `${turn.role === "agent" ? "You" : "Customer"}: ${turn.text.slice(0, 300)}`)
    : [];

  const system = [
    `You are ${preset.assistant}, answering customers for this business:`,
    preset.description,
    "",
    "Warm, brief, two or three lines at most. No preamble.",
    "Answer only from the description above. Never invent a price, an hour or a service that is not listed.",
    ESCALATION_RULE,
    "If it fits, offer to book them in and ask for a phone number.",
    "If they ask for something the business does not do, say so plainly.",
    "Reply in the language the customer wrote in.",
  ].join("\n");

  try {
    const answer = await ask({
      system,
      user: history.length ? [...history, `Customer: ${message}`].join("\n") : message,
      temperature: 0.4,
      maxTokens: 400,
      weight: weigh(message),
    });

    const reply = answer.unsure
      ? "That one is beyond what I have been told. What is the best number to reach you on, and someone will call back?"
      : tidyText(answer.text.replaceAll(UNSURE, "")).slice(0, 600);

    return NextResponse.json({ reply });
  } catch {
    return NextResponse.json({ reply: "The demo is busy right now. Try again in a moment." });
  }
}
