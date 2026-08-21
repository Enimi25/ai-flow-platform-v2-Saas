import path from "node:path";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import type { Call, Outcome } from "./types";

const FILE = path.join(process.cwd(), ".data", "calls.json");
const readAll = () => readJson<Call[]>(FILE, []);

export async function listCalls(companyId: string) {
  return (await readAll())
    .filter((call) => call.companyId === companyId)
    .sort((a, b) => {
      // anything still to do first, soonest due at the top
      if (a.status === "done" && b.status !== "done") return 1;
      if (b.status === "done" && a.status !== "done") return -1;
      return a.dueAt.localeCompare(b.dueAt);
    });
}

export async function getCall(id: string) {
  return (await readAll()).find((call) => call.id === id) ?? null;
}

export function saveCall(call: Call) {
  return withFileLock(FILE, async () => {
    const all = await readAll();
    const at = all.findIndex((item) => item.id === call.id);
    if (at >= 0) all[at] = call;
    else all.unshift(call);
    await writeJson(FILE, all.slice(0, 2_000));
    return call;
  });
}

export function deleteCall(id: string) {
  return withFileLock(FILE, async () => {
    await writeJson(FILE, (await readAll()).filter((call) => call.id !== id));
  });
}

/** One open call per phone number, so a lead is never queued twice. */
export async function alreadyQueued(companyId: string, phone: string) {
  const digits = phone.replace(/\D/g, "");
  return (await readAll()).some(
    (call) =>
      call.companyId === companyId &&
      call.status !== "done" &&
      call.phone.replace(/\D/g, "") === digits,
  );
}

export async function callStats(companyId: string) {
  const calls = await listCalls(companyId);
  const done = calls.filter((call) => call.status === "done");
  const reached = done.filter((call) => call.outcome && call.outcome !== "no_answer");
  const booked = done.filter((call) => call.outcome === "booked");

  return {
    waiting: calls.filter((call) => call.status !== "done").length,
    called: done.length,
    reached: reached.length,
    booked: booked.length,
    /** Of the people actually reached, how many booked. */
    conversion: reached.length ? Math.round((booked.length / reached.length) * 100) : 0,
  };
}

export const isOutcome = (value: unknown): value is Outcome =>
  typeof value === "string" && ["booked", "callback", "not_interested", "wrong_number", "no_answer"].includes(value);
