export const OUTCOMES = ["booked", "callback", "not_interested", "wrong_number", "no_answer"] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const OUTCOME_LABEL: Record<Outcome, string> = {
  booked: "Booked",
  callback: "Call back later",
  not_interested: "Not interested",
  wrong_number: "Wrong number",
  no_answer: "No answer",
};

export type CallStatus = "queued" | "calling" | "done";

export type Call = {
  id: string;
  companyId: string;
  leadId?: string;
  name: string;
  phone: string;
  /** Why this person is worth a call, in one line. */
  reason: string;
  /** What the agent already discussed with them, so the caller is not blind. */
  context: string;
  script?: CallScript;
  status: CallStatus;
  outcome?: Outcome;
  notes?: string;
  attempts: number;
  /** Set when a callback was agreed, so the queue re-surfaces it. */
  dueAt: string;
  createdAt: string;
  completedAt?: string;
};

/** What to say, written for this one person rather than a generic sheet. */
export type CallScript = {
  opening: string;
  points: string[];
  objections: { heard: string; answer: string }[];
  closing: string;
  generatedAt: string;
};
