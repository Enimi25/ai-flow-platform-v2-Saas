import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import { sendEmail, isEmailReady } from "./send";
import { followUpEmail, type Step } from "./follow-up";
import { safeRecord } from "@/lib/activity";
import { dataFile } from "@/lib/data-dir";

/**
 * What happens after the proposal.
 *
 * One email and silence is how most of these die. Somebody asks for a demo on a
 * Tuesday, reads the proposal on their phone between customers, means to come
 * back to it, and never does — not because they said no, but because nobody
 * asked twice.
 *
 * Four touches over three weeks, each carrying something new rather than
 * "just checking in". Any reply stops the sequence: the point is to reach
 * people who went quiet, not to keep talking at people who answered.
 */

export type Enrolled = {
  id: string;
  email: string;
  name: string;
  /** What they told us they do, so later mails can stay specific. */
  business: string;
  companyId: string;
  startedAt: string;
  /** Steps already sent, by day number. */
  sent: number[];
  stoppedAt?: string;
  stopReason?: "replied" | "converted" | "unsubscribed" | "finished";
};

const FILE = dataFile("sequence.json");
const readAll = () => readJson<Enrolled[]>(FILE, []);

/** Day offset, and what that mail is for. */
export const STEPS: { day: number; step: Step }[] = [
  { day: 3, step: "nudge" },
  { day: 7, step: "proof" },
  { day: 14, step: "objection" },
  { day: 21, step: "last" },
];

export async function enrol(input: Omit<Enrolled, "id" | "startedAt" | "sent">) {
  return withFileLock(FILE, async () => {
    const all = await readAll();
    // one sequence per address, however many times they fill the form
    if (all.some((row) => row.email === input.email && !row.stoppedAt)) return null;

    const row: Enrolled = {
      ...input,
      id: crypto.randomUUID(),
      startedAt: new Date().toISOString(),
      sent: [],
    };
    await writeJson(FILE, [...all, row].slice(-2_000));
    return row;
  });
}

/** Anything from them ends it. Silence is the only thing worth following up. */
export async function stopFor(email: string, reason: Enrolled["stopReason"]) {
  return withFileLock(FILE, async () => {
    const all = await readAll();
    let touched = false;
    for (const row of all) {
      if (row.email === email.toLowerCase() && !row.stoppedAt) {
        row.stoppedAt = new Date().toISOString();
        row.stopReason = reason;
        touched = true;
      }
    }
    if (touched) await writeJson(FILE, all);
    return touched;
  });
}

const DAY = 24 * 60 * 60 * 1000;

/** Called by the scheduler. Sends whatever has come due, one mail at a time. */
export async function runSequence(now = Date.now()) {
  if (!isEmailReady()) return { sent: 0, skipped: "email not configured" as const };

  const all = await readAll();
  const due: { row: Enrolled; day: number; step: Step }[] = [];

  for (const row of all) {
    if (row.stoppedAt) continue;
    const age = now - new Date(row.startedAt).getTime();

    for (const { day, step } of STEPS) {
      if (row.sent.includes(day)) continue;
      if (age < day * DAY) break;
      // only the earliest unsent step, so a long-dormant record does not
      // receive four emails in one minute
      due.push({ row, day, step });
      break;
    }
  }

  let sent = 0;
  for (const { row, day, step } of due) {
    const site = process.env.PUBLIC_SITE_URL || "https://aiflow.forum";
    try {
      await sendEmail({
        to: row.email,
        subject: subjectFor(step, row.name) ?? "AI FLOW",
        replyTo: process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com",
        html: followUpEmail({
          step,
          name: row.name,
          business: row.business,
          siteUrl: site,
          contactEmail: process.env.EMAIL_REPLY_TO || "baskinltd@yahoo.com",
        }),
      });

      await withFileLock(FILE, async () => {
        const rows = await readAll();
        const found = rows.find((item) => item.id === row.id);
        if (!found) return;
        found.sent.push(day);
        if (day === STEPS[STEPS.length - 1].day) {
          found.stoppedAt = new Date().toISOString();
          found.stopReason = "finished";
        }
        await writeJson(FILE, rows);
      });

      sent += 1;
      safeRecord({
        companyId: row.companyId,
        kind: "email.followup",
        level: "info",
        title: `Follow up sent, day ${day}`,
        detail: row.email,
      });
    } catch (error) {
      safeRecord({
        companyId: row.companyId,
        kind: "email.failed",
        level: "error",
        title: `Follow up did not send`,
        detail: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return { sent, skipped: null };
}

function subjectFor(step: Step, name: string) {
  const who = name ? `${name}, ` : "";
  switch (step) {
    case "nudge":
      return `${who}your agent is still built and waiting`;
    case "proof":
      return `${who}what it caught for someone else last week`;
    case "objection":
      return `${who}the three things people ask before saying yes`;
    case "last":
      return `${who}closing this off`;
  }
}
