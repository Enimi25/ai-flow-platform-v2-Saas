import { claimDuePosts, getPost, savePost } from "./store";
import { publish } from "./publishers";
import type { Post } from "./types";
import { safeRecord } from "@/lib/activity";

async function send(post: Post): Promise<Post> {
  const result = await publish(post);
  const settled: Post = result.ok
    ? { ...post, status: "published", externalId: result.externalId, publishedAt: new Date().toISOString(), error: undefined }
    : { ...post, status: "failed", error: result.error };

  safeRecord({
    companyId: post.companyId,
    kind: result.ok ? "content.published" : "content.failed",
    level: result.ok ? "success" : "error",
    title: result.ok
      ? `Posted to ${post.channel}${result.externalId.startsWith("dry-run") ? " (dry run)" : ""}`
      : `${post.channel} post did not go out`,
    detail: result.ok ? post.body.slice(0, 90).replace(/\n/g, " ") : result.error,
  });

  return savePost(settled);
}

/** Publish one post immediately, whatever its schedule said. */
export async function publishNow(id: string): Promise<Post | null> {
  const post = await getPost(id);
  if (!post) return null;
  return send({ ...post, status: "publishing" });
}

/** Everything whose moment has arrived. Called by the scheduler. */
export async function runDue(now = new Date()) {
  const due = await claimDuePosts(now);
  const settled = await Promise.all(due.map(send));
  return {
    picked: due.length,
    published: settled.filter((post) => post.status === "published").length,
    failed: settled.filter((post) => post.status === "failed").length,
    posts: settled,
  };
}
