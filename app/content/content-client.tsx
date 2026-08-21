"use client";

import { useCallback, useEffect, useState } from "react";
import { PaperPlaneTilt, Clock, CheckCircle, WarningCircle, Sparkle, FilmSlate, Trash, ThumbsUp } from "@phosphor-icons/react";
import { CHANNELS, CHANNEL_LABEL, REQUIRES_MEDIA, type Channel, type Post } from "@/lib/content/types";
import s from "./content.module.css";

type Readiness = Record<Channel, { ready: boolean; missing: string[] }>;

const STATUS_ICON = {
  scheduled: Clock,
  publishing: Clock,
  published: CheckCircle,
  failed: WarningCircle,
  draft: Clock,
} as const;

function localNow() {
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  return now.toISOString().slice(0, 16);
}

export function ContentClient({ canPost }: { canPost: boolean }) {
  const [posts, setPosts] = useState<Post[]>([]);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [channel, setChannel] = useState<Channel>("facebook");
  const [body, setBody] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [scheduledAt, setScheduledAt] = useState(localNow);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch("/api/content");
    if (!response.ok) return;
    const data = await response.json();
    setPosts(data.posts);
    setReadiness(data.readiness);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function queue(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const response = await fetch("/api/content", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, body, mediaUrl, scheduledAt: new Date(scheduledAt).toISOString() }),
    });
    const data = await response.json();
    setBusy(false);
    if (!response.ok) {
      setMessage(data.error ?? "Could not queue that post.");
      return;
    }
    setBody("");
    setMediaUrl("");
    setMessage("Queued.");
    void load();
  }

  async function generate(format: "post" | "reel") {
    setGenerating(true);
    setMessage("");
    const response = await fetch("/api/content/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel, count: 5, format }),
    });
    const data = await response.json();
    setGenerating(false);
    setMessage(
      response.ok
        ? `The agent wrote ${data.posts.length} ${format === "reel" ? "reel scripts" : "drafts"}.`
        : data.error ?? "Could not generate.",
    );
    void load();
  }

  async function approve(id: string) {
    setBusy(true);
    await fetch("/api/content/status", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, status: "scheduled" }),
    });
    setBusy(false);
    void load();
  }

  async function remove(id: string) {
    setBusy(true);
    await fetch("/api/content/status", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    setBusy(false);
    void load();
  }

  async function publishNow(id: string) {
    setBusy(true);
    const response = await fetch("/api/content/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    const data = await response.json();
    setBusy(false);
    setMessage(response.ok ? "Sent." : data.post?.error ?? data.error ?? "Publishing failed.");
    void load();
  }

  const notReady = readiness
    ? (Object.keys(readiness) as Channel[]).filter((key) => !readiness[key].ready)
    : [];

  return (
    <div className={s.wrap}>
      {notReady.length > 0 && (
        <div className={s.notice}>
          <WarningCircle size={20} weight="fill" />
          <div>
            <b>Not connected yet: {notReady.map((key) => CHANNEL_LABEL[key]).join(", ")}</b>
            <p>
              Posts still queue and schedule. They go out as soon as the missing credentials are set:{" "}
              <code>{Array.from(new Set(notReady.flatMap((key) => readiness![key].missing))).join(", ")}</code>
            </p>
          </div>
        </div>
      )}

      <div className={s.board}>
        <form className={s.composer} onSubmit={queue}>
          <h2>Queue a post</h2>

          <div className={s.channels} role="radiogroup" aria-label="Channel">
            {CHANNELS.map((key) => (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={channel === key}
                className={channel === key ? s.channelOn : s.channel}
                onClick={() => setChannel(key)}
              >
                {CHANNEL_LABEL[key]}
              </button>
            ))}
          </div>

          <label htmlFor="post-body">Post text</label>
          <textarea
            id="post-body"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="What goes out?"
            rows={5}
            required
          />

          <label htmlFor="post-media">
            Media URL {REQUIRES_MEDIA[channel] ? "(required here)" : "(optional)"}
          </label>
          <input
            id="post-media"
            type="url"
            value={mediaUrl}
            onChange={(event) => setMediaUrl(event.target.value)}
            placeholder="https://..."
            required={REQUIRES_MEDIA[channel]}
          />

          <label htmlFor="post-when">Send at</label>
          <input
            id="post-when"
            type="datetime-local"
            value={scheduledAt}
            onChange={(event) => setScheduledAt(event.target.value)}
            required
          />

          <button className="btn" type="submit" disabled={busy || !canPost}>
            <PaperPlaneTilt weight="fill" /> {canPost ? "Add to queue" : "Sign in to queue"}
          </button>
          <div className={s.generateRow}>
            <button
              type="button"
              className={s.generate}
              onClick={() => generate("post")}
              disabled={generating || !canPost}
              title="Five posts about your business, written by the agent"
            >
              <Sparkle weight="fill" /> {generating ? "Writing…" : "5 posts"}
            </button>
            <button
              type="button"
              className={s.generate}
              onClick={() => generate("reel")}
              disabled={generating || !canPost}
              title="Five reels with a shot list you can film on a phone"
            >
              <FilmSlate weight="fill" /> {generating ? "Writing…" : "5 reels"}
            </button>
          </div>
          <p className={s.message}>{message}</p>
        </form>

        <section className={s.queue}>
          <h2>Queue</h2>
          {posts.length === 0 ? (
            <div className={s.empty}>
              <p>Nothing queued yet. The first post you add shows up here with its status.</p>
            </div>
          ) : (
            <ul>
              {posts.map((post) => {
                const Icon = STATUS_ICON[post.status];
                return (
                  <li key={post.id} data-status={post.status}>
                    <div className={s.meta}>
                      <span className={s.badge}>{CHANNEL_LABEL[post.channel]}</span>
                      <span className={`${s.status} num`}>
                        <Icon size={14} weight="fill" /> {post.status}
                      </span>
                      <time className="num" dateTime={post.scheduledAt}>
                        {new Date(post.scheduledAt).toLocaleString()}
                      </time>
                    </div>
                    <p className={s.body}>{post.body}</p>
                    {post.error && <p className={s.error}>{post.error}</p>}
                    <div className={s.rowActions}>
                      {post.status === "draft" && (
                        <button type="button" className={s.approve} onClick={() => approve(post.id)} disabled={busy}>
                          <ThumbsUp size={14} weight="fill" /> Approve
                        </button>
                      )}
                      {post.status !== "published" && (
                        <button type="button" className={s.send} onClick={() => publishNow(post.id)} disabled={busy}>
                          Send now
                        </button>
                      )}
                      {post.status !== "published" && (
                        <button type="button" className={s.send} onClick={() => remove(post.id)} disabled={busy} aria-label="Delete">
                          <Trash size={14} />
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
