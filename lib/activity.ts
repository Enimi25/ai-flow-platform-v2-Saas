import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import { dataFile } from "@/lib/data-dir";

export type Level = "info" | "success" | "warn" | "error";

export type Event = {
  id: string;
  companyId: string;
  at: string;
  kind: string;
  title: string;
  detail?: string;
  level: Level;
};

const FILE = dataFile("activity.json");
const KEEP = 500;

const readAll = () => readJson<Event[]>(FILE, []);

/**
 * Every meaningful thing the workspace does lands here, so the customer can see
 * the system working instead of guessing.
 */
export function record(event: Omit<Event, "id" | "at">) {
  return withFileLock(FILE, async () => {
    const all = await readAll();
    all.unshift({ ...event, id: crypto.randomUUID(), at: new Date().toISOString() });
    await writeJson(FILE, all.slice(0, KEEP));
  });
}

export async function listEvents(companyId: string, limit = 120) {
  return (await readAll()).filter((event) => event.companyId === companyId).slice(0, limit);
}

/** Never let logging break the thing it is logging. */
export function safeRecord(event: Omit<Event, "id" | "at">) {
  void record(event).catch(() => {});
}
