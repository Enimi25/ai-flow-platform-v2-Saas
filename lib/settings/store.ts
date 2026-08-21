import { promises as fs } from "node:fs";
import path from "node:path";

export * from "./options";
import { INDUSTRIES, TONES, GOALS, DEFAULT_HOURS, type Settings } from "./options";

const FILE = path.join(process.cwd(), ".data", "settings.json");

export function defaults(companyId: string): Settings {
  return {
    companyId,
    companyName: "",
    industry: INDUSTRIES[0],
    website: "",
    phone: "",
    assistantName: "Flo",
    tone: TONES[0],
    goal: GOALS[0],
    welcome: "Hi. What can I help you with today?",
    leadQuestion: "What is the best phone number or email to reach you?",
    businessDescription: "",
    openingHours: DEFAULT_HOURS,
    slotMinutes: 60,
    timezone: "Europe/London",
    bookingEnabled: true,
    contentAuto: false,
    contentPerWeek: 7,
    updatedAt: new Date().toISOString(),
  };
}

async function readAll(): Promise<Record<string, Settings>> {
  try {
    return JSON.parse(await fs.readFile(FILE, "utf8"));
  } catch {
    return {};
  }
}

/** Older records predate opening hours, so read through the defaults. */
export async function getSettings(companyId: string) {
  const stored = (await readAll())[companyId];
  return stored ? { ...defaults(companyId), ...stored } : defaults(companyId);
}

export async function saveSettings(settings: Settings) {
  const all = await readAll();
  all[settings.companyId] = { ...settings, updatedAt: new Date().toISOString() };
  await fs.mkdir(path.dirname(FILE), { recursive: true });
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
  return all[settings.companyId];
}
