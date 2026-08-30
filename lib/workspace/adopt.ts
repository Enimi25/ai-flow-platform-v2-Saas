import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import { dataFile } from "@/lib/data-dir";

const FILES = ["leads.json", "conversations.json", "activity.json", "bookings.json", "content.json"];

/**
 * Hands the house records to the account that owns the platform.
 *
 * Before accounts existed, everything from our own site was filed under a
 * literal "preview" — a workspace no account owns. The data was never lost, but
 * it was invisible to the one person entitled to see it. The first account to
 * register adopts it.
 */
export async function adoptPreviewRecords(companyId: string) {
  if (!companyId || companyId === "preview") return 0;
  let moved = 0;

  for (const name of FILES) {
    const file = dataFile(name);
    await withFileLock(file, async () => {
      const rows = await readJson<Array<Record<string, unknown>>>(file, []);
      if (!Array.isArray(rows) || !rows.length) return;

      let touched = false;
      for (const row of rows) {
        if (row && row.companyId === "preview") {
          row.companyId = companyId;
          touched = true;
          moved += 1;
        }
      }
      if (touched) await writeJson(file, rows);
    }).catch(() => {});
  }

  return moved;
}
