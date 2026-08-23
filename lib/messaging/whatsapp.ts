import { connectionFor } from "@/lib/content/connections";

const GRAPH = "https://graph.facebook.com/v21.0";

/** Send a text reply through the WhatsApp Cloud API. */
export async function sendWhatsAppMessage(input: { companyId: string; to: string; text: string }) {
  const link = await connectionFor(input.companyId, "whatsapp");
  if (!link?.accountId) throw new Error(`WhatsApp is not connected for ${input.companyId}`);

  const response = await fetch(`${GRAPH}/${encodeURIComponent(link.accountId)}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${link.accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to: input.to,
      type: "text",
      text: { body: input.text.slice(0, 4096) },
    }),
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.error?.message ?? `WhatsApp send failed ${response.status}`);
  return payload as { messages?: Array<{ id?: string }> };
}
