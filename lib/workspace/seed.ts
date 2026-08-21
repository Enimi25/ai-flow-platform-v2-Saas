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
  "Prices, which you may always quote:",
  "  Website Agent — $39 per month. The agent on your website: answers, captures leads, books.",
  "  Connected Sales — $99 per month. Everything above plus Messenger, Instagram and the content factory.",
  "  Growth Partner — custom price, quoted after a call. We work the funnel with you.",
  "Setup is one line of code pasted into the site. No plugin and no rebuild.",
  "",
  "What it will not do: invent a price, promise a time that is not free, or ask for a",
  "password or card number. When it does not know, it says so and takes a contact.",
  "",
  "",
  "Hours: the agent itself runs 24 hours a day, 7 days a week, including Sundays and holidays.",
  "That is the point of it. Our own team answers on weekdays, but nothing waits for us.",
  "",
  "Setup time: most sites are answering customers the same day.",
  "Languages: any. It replies in whatever language the customer wrote in.",
  "Free to try. No card needed. To stop, delete the line from your site and cancel.",
  "",
  "Site: https://aiflow.forum. Contact: baskinltd@yahoo.com.",
].join("\n");

/** A line only our own text carries, so an owner's edits are never overwritten. */
const OURS = "AI FLOW puts an AI sales agent";

export async function seedHouseWorkspace() {
  const companyId = await houseCompanyId();
  if (companyId === "preview") return false;

  const settings = await getSettings(companyId);
  const existing = settings.businessDescription;

  // Replace only text we wrote ourselves. Anything the owner typed stands.
  if (existing && !(existing.startsWith(OURS) && existing !== ABOUT)) return false;

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
