import { getSettings, saveSettings } from "@/lib/settings/store";
import { houseCompanyId } from "./store";

/**
 * Describes AI FLOW to its own agent, once.
 *
 * The platform is a customer of itself: the same content factory that writes for
 * a salon should write for us. It cannot do that without a description to work
 * from, and the owner should not have to type out their own product to get it.
 *
 * Idempotent — it only fills a workspace that has nothing, so anything the owner
 * writes later stands.
 */
const ABOUT = [
  "AI FLOW puts an AI sales agent on a small business's website and messengers.",
  "The agent answers customer questions in seconds, in whatever language they wrote in,",
  "keeps their contact details, and books the appointment against the real opening hours.",
  "It works on the website, Facebook Messenger, Instagram and WhatsApp.",
  "",
  "Plans: Website Agent 39/month. Connected Sales 99/month. Growth Partner is custom.",
  "Setup is one line of code pasted into the site. No plugin and no rebuild.",
  "",
  "What it will not do: invent a price, promise a time that is not free, or ask for a",
  "password or card number. When it does not know, it says so and takes a contact.",
  "",
  "Site: https://aiflow.forum. Contact: baskinltd@yahoo.com.",
].join("\n");

export async function seedHouseWorkspace() {
  const companyId = await houseCompanyId();
  if (companyId === "preview") return false;

  const settings = await getSettings(companyId);
  if (settings.businessDescription) return false;

  await saveSettings({
    ...settings,
    companyName: "AI FLOW",
    assistantName: "Flo",
    website: "https://aiflow.forum",
    businessDescription: ABOUT,
    contentAuto: true,
    contentPerWeek: 3,
  });
  return true;
}
