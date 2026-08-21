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
  updatedAt: string;
};
