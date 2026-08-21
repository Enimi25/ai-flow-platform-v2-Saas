import path from "node:path";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";

/**
 * Erases everything one person left behind.
 *
 * Called both by Meta's deletion callback and by anyone exercising the right to
 * be forgotten. It removes rather than flags: a record kept with a "deleted"
 * column is not deleted, and saying otherwise on a compliance form is worse than
 * not answering it.
 */
const TARGETS: { file: string; matches: (row: Record<string, unknown>, id: string) => boolean }[] = [
  { file: "conversations.json", matches: (row, id) => row.visitorId === id },
  { file: "leads.json", matches: (row, id) => row.visitorId === id || row.externalId === id },
  { file: "calls.json", matches: (row, id) => row.leadId === id },
  { file: "bookings.json", matches: (row, id) => row.customerName === id || row.customerEmail === id },
];

export async function forgetVisitor(visitorId: string) {
  if (!visitorId) return 0;
  let removed = 0;

  for (const target of TARGETS) {
    const file = path.join(process.cwd(), ".data", target.file);
    await withFileLock(file, async () => {
      const rows = await readJson<Record<string, unknown>[]>(file, []);
      if (!Array.isArray(rows) || !rows.length) return;

      const kept = rows.filter((row) => !target.matches(row, visitorId));
      if (kept.length !== rows.length) {
        removed += rows.length - kept.length;
        await writeJson(file, kept);
      }
    }).catch(() => {});
  }

  return removed;
}
