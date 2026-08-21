/**
 * Businesses a visitor can try the agent as, without signing up.
 *
 * These live on the server and are chosen by key, never sent from the browser
 * as free text. A visitor who could post their own business description could
 * post their own instructions, and the widget would follow them.
 */
export type PresetKey = "salon" | "clinic" | "workshop";

export type Preset = {
  key: PresetKey;
  label: string;
  assistant: string;
  description: string;
  /** Questions this trade actually gets, offered as one-tap starters. */
  starters: string[];
};

export const PRESETS: Record<PresetKey, Preset> = {
  salon: {
    key: "salon",
    label: "Hair salon",
    assistant: "Ava",
    description: [
      "Aurora, a hair salon on Oxford Street.",
      "Cut and finish 45. Colour from 110. Balayage from 180. Blow dry 30.",
      "Open Tuesday to Sunday, 10:00 to 20:00. Closed Mondays.",
      "Four stylists. Saturday books up about ten days ahead, weekdays usually have space next day.",
      "Card and cash. Cancellations are free up to 24 hours before.",
    ].join("\n"),
    starters: ["How much is a cut?", "Anything free on Saturday?", "Do you do balayage?"],
  },
  clinic: {
    key: "clinic",
    label: "Dental clinic",
    assistant: "Nora",
    description: [
      "Bright Smile, a dental clinic in the town centre.",
      "Check-up 60. Hygienist clean 85. White filling from 140. Whitening 320.",
      "Open Monday to Friday 09:00 to 18:00, Saturday 10:00 to 14:00.",
      "Emergency slots are held back every morning for pain.",
      "We do not take walk-ins. Insurance: we invoice, patients claim it back themselves.",
    ].join("\n"),
    starters: ["How much is a cleaning?", "I have toothache today", "Do you take insurance?"],
  },
  workshop: {
    key: "workshop",
    label: "Car workshop",
    assistant: "Sam",
    description: [
      "Meridian Motors, an independent car workshop.",
      "Diagnostics 40, refunded against any repair. Brake pads from 160 fitted. Full service 240. MOT 55.",
      "Open Monday to Friday 08:00 to 18:00, Saturday 08:00 to 13:00.",
      "Courtesy car available if booked three days ahead.",
      "We do not work on electric vehicles or motorcycles.",
    ].join("\n"),
    starters: ["My brakes squeal", "How much is a service?", "Can I get a courtesy car?"],
  },
};

export function presetFor(key: unknown): Preset | null {
  return typeof key === "string" && key in PRESETS ? PRESETS[key as PresetKey] : null;
}
