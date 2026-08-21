/**
 * The telephony leg, which is deliberately not connected yet.
 *
 * Everything around the call — the queue, the brief, the outcome, what it does
 * to the lead — works without a phone line and is useful on its own: whoever
 * picks up the handset already knows what this person asked and what was
 * answered. The provider is the last piece, not the first.
 *
 * When one is chosen it needs bidirectional media streaming over WebSocket, not
 * just the ability to place a call. A provider that can only dial and play a
 * recording cannot hold a conversation, and the difference is not obvious from
 * a pricing page.
 */

export type ProviderStatus = {
  provider: string | null;
  missing: string[];
  /** What the outbound leg still needs before a call can be placed. */
  needs: { name: string; done: boolean; note: string }[];
};

const KEYS = ["TELEPHONY_PROVIDER", "TELEPHONY_API_KEY", "TELEPHONY_NUMBER", "TTS_API_KEY"];

export function isTelephonyReady() {
  return KEYS.every((key) => Boolean(process.env[key]));
}

export function providerStatus(): ProviderStatus {
  const has = (key: string) => Boolean(process.env[key]);

  return {
    provider: process.env.TELEPHONY_PROVIDER ?? null,
    missing: KEYS.filter((key) => !has(key)),
    needs: [
      {
        name: "A number that can stream audio",
        done: has("TELEPHONY_API_KEY") && has("TELEPHONY_NUMBER"),
        note: "Bidirectional media over WebSocket. Dial-and-play is not enough to hold a conversation.",
      },
      {
        name: "A voice that does not sound like a machine",
        done: has("TTS_API_KEY"),
        note: "Neural speech with real prosody. This is what decides whether people stay on the line.",
      },
      {
        name: "Hearing the customer",
        done: true,
        note: "Already working: Whisper, on the key this workspace already uses. Nothing to pay for.",
      },
      {
        name: "Knowing what to say",
        done: true,
        note: "Already working: the brief is written from this customer's own conversation.",
      },
    ],
  };
}
