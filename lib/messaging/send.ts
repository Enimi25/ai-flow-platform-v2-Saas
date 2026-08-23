import { connectionFor } from "@/lib/content/connections";
import type { Channel } from "@/lib/content/types";

const GRAPH = "https://graph.facebook.com/v21.0";

/**
 * The connected Page or Instagram Business account sends on behalf of the
 * business. Instagram requires its business account id rather than `/me`.
 */
export async function sendMessage(input: {
  companyId: string;
  channel: Extract<Channel, "facebook" | "instagram">;
  to: string;
  text: string;
}) {
  const link = await connectionFor(input.companyId, input.channel);
  if (!link) throw new Error(`${input.channel} is not connected for ${input.companyId}`);

  const response = await fetch(
    `${GRAPH}/${encodeURIComponent(link.accountId || "me")}/messages?access_token=${encodeURIComponent(link.accessToken)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient: { id: input.to },
        message: { text: input.text.slice(0, 900) },
        ...(input.channel === "facebook" ? { messaging_type: "RESPONSE" } : {}),
      }),
    },
  );

  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.error?.message ?? `send failed ${response.status}`);
  return payload as { message_id?: string };
}
