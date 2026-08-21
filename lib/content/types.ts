export const CHANNELS = ["facebook", "instagram", "tiktok"] as const;
export type Channel = (typeof CHANNELS)[number];

export type PostStatus = "draft" | "scheduled" | "publishing" | "published" | "failed";

export type Post = {
  id: string;
  companyId: string;
  channel: Channel;
  body: string;
  /** Instagram and TikTok will not accept a post without media. */
  mediaUrl?: string;
  /** ISO timestamp. A post is picked up once this moment has passed. */
  scheduledAt: string;
  status: PostStatus;
  externalId?: string;
  publishedAt?: string;
  error?: string;
  createdAt: string;
};

export const CHANNEL_LABEL: Record<Channel, string> = {
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
};

/** Media is optional on a Page post, required by the other two. */
export const REQUIRES_MEDIA: Record<Channel, boolean> = {
  facebook: false,
  instagram: true,
  tiktok: true,
};
