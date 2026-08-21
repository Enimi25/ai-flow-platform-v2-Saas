import path from "node:path";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";

export type Turn = { role: "customer" | "agent"; text: string; at: string };

export type Conversation = {
  id: string;
  companyId: string;
  visitorId: string;
  source: string;
  turns: Turn[];
  startedAt: string;
  lastAt: string;
  leadId?: string;
};

const FILE = path.join(process.cwd(), ".data", "conversations.json");
const KEEP_TURNS = 60;

const readAll = () => readJson<Conversation[]>(FILE, []);

const writeAll = (items: Conversation[]) => writeJson(FILE, items);

export async function listConversations(companyId: string) {
  return (await readAll())
    .filter((thread) => thread.companyId === companyId)
    .sort((a, b) => b.lastAt.localeCompare(a.lastAt));
}

/**
 * The tail of a visitor's thread, oldest first.
 *
 * Without this the model sees one message at a time and has no idea it already
 * asked for a phone number, so it asks again — which is exactly how a helpful
 * assistant turns into a form.
 */
export async function recentTurns(companyId: string, visitorId: string, limit = 10) {
  const thread = (await readAll()).find(
    (item) => item.companyId === companyId && item.visitorId === visitorId,
  );
  return (thread?.turns ?? []).filter((turn) => turn.text !== "[contact captured]").slice(-limit);
}

/** One thread per visitor, so a returning customer continues instead of starting over. */
export function appendTurn(input: {
  companyId: string;
  visitorId: string;
  source?: string;
  turn: Turn;
  leadId?: string;
}) {
  // appendTurn
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const now = input.turn.at;
  let thread = all.find(
    (entry) => entry.companyId === input.companyId && entry.visitorId === input.visitorId,
  );

  if (!thread) {
    thread = {
      id: crypto.randomUUID(),
      companyId: input.companyId,
      visitorId: input.visitorId,
      source: input.source ?? "website",
      turns: [],
      startedAt: now,
      lastAt: now,
    };
    all.unshift(thread);
  }

  thread.turns.push(input.turn);
  if (thread.turns.length > KEEP_TURNS) thread.turns = thread.turns.slice(-KEEP_TURNS);
  thread.lastAt = now;
  if (input.leadId) thread.leadId = input.leadId;

  await writeAll(all);
  return thread;
  });
}
