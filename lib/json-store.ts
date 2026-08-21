import { promises as fs } from "node:fs";
import path from "node:path";

/**
 * Every store here is a read, modify, write over one JSON file. Two of those
 * running at once interleave and leave the file unparseable, which is exactly
 * what happened when the scheduler published several posts in parallel.
 *
 * Work is queued per file, and the write goes to a temporary file that is then
 * renamed, so a reader never sees a half written document.
 */
const queues = new Map<string, Promise<unknown>>();

export function withFileLock<T>(file: string, work: () => Promise<T>): Promise<T> {
  const previous = queues.get(file) ?? Promise.resolve();
  const next = previous.then(work, work);
  // keep the chain alive even if this piece of work rejected
  queues.set(file, next.catch(() => undefined));
  return next;
}

export async function readJson<T>(file: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await fs.readFile(file, "utf8")) as T;
  } catch {
    return fallback;
  }
}

export async function writeJson(file: string, value: unknown) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const temporary = `${file}.${process.pid}.tmp`;
  await fs.writeFile(temporary, JSON.stringify(value, null, 2), "utf8");
  await fs.rename(temporary, file);
}

/** Read, change, and write one file without anything else touching it meanwhile. */
export function mutate<T, R>(file: string, fallback: T, change: (current: T) => R | Promise<R>, pick: (current: T, result: R) => T) {
  return withFileLock(file, async () => {
    const current = await readJson<T>(file, fallback);
    const result = await change(current);
    await writeJson(file, pick(current, result));
    return result;
  });
}
