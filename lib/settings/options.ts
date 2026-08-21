/** Client safe. The store next door touches the filesystem and cannot be imported into a browser bundle. */
export const INDUSTRIES = [
  "Beauty and salon",
  "Dental and medical",
  "Auto service",
  "Fitness and wellness",
  "Home services",
  "Restaurant and cafe",
  "Retail",
  "Professional services",
  "Other",
] as const;

export const TONES = ["Friendly", "Direct", "Formal", "Warm"] as const;
export const GOALS = ["Capture leads", "Book appointments", "Answer questions", "Qualify and hand over"] as const;

/** Wall-clock opening times for one day, or null when the business is shut. */
export type DayHours = { open: string; close: string } | null;

export type OpeningHours = {
  mon: DayHours; tue: DayHours; wed: DayHours;
  thu: DayHours; fri: DayHours; sat: DayHours; sun: DayHours;
};

export const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type DayKey = (typeof DAY_KEYS)[number];

export const DEFAULT_HOURS: OpeningHours = {
  mon: { open: "09:00", close: "18:00" },
  tue: { open: "09:00", close: "18:00" },
  wed: { open: "09:00", close: "18:00" },
  thu: { open: "09:00", close: "18:00" },
  fri: { open: "09:00", close: "18:00" },
  sat: null,
  sun: null,
};

export type Settings = {
  companyId: string;
  companyName: string;
  industry: string;
  website: string;
  phone: string;
  assistantName: string;
  tone: string;
  goal: string;
  welcome: string;
  leadQuestion: string;
  businessDescription: string;
  /** Everything the agent needs to offer a real time rather than a vague one. */
  openingHours: OpeningHours;
  slotMinutes: number;
  timezone: string;
  bookingEnabled: boolean;
  updatedAt: string;
};
