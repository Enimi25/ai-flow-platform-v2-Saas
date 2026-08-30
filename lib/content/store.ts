import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import type { Post } from "./types";
import { dataFile } from "@/lib/data-dir";

/**
 * File backed for now. Every read and write goes through this module, so
 * moving to Postgres is a change here and nowhere else.
 */
const FILE = dataFile("content.json");

const readAll = () => readJson<Post[]>(FILE, []);
const writeAll = (posts: Post[]) => writeJson(FILE, posts);

export async function listPosts(companyId: string): Promise<Post[]> {
  const all = await readAll();
  return all
    .filter((post) => post.companyId === companyId)
    .sort((a, b) => b.scheduledAt.localeCompare(a.scheduledAt));
}

export async function getPost(id: string): Promise<Post | null> {
  return (await readAll()).find((post) => post.id === id) ?? null;
}

export function savePost(post: Post): Promise<Post> {
  return withFileLock(FILE, async () => {
    const all = await readAll();
    const index = all.findIndex((entry) => entry.id === post.id);
    if (index === -1) all.push(post);
    else all[index] = post;
    await writeAll(all);
    return post;
  });
}

export function deletePost(id: string): Promise<void> {
  return withFileLock(FILE, async () => {
    await writeAll((await readAll()).filter((post) => post.id !== id));
  });
}

/** Everything scheduled whose moment has passed and that has not gone out yet. */
export function claimDuePosts(now = new Date()): Promise<Post[]> {
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const due = all.filter(
    (post) => post.status === "scheduled" && new Date(post.scheduledAt) <= now,
  );
  if (!due.length) return [];

  const claimed = new Set(due.map((post) => post.id));
  await writeAll(
    all.map((post) => (claimed.has(post.id) ? { ...post, status: "publishing" as const } : post)),
  );
  return due.map((post) => ({ ...post, status: "publishing" as const }));
  });
}
