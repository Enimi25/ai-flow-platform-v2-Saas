import type { MetadataRoute } from "next";
export default function sitemap(): MetadataRoute.Sitemap { return [{ url: "https://aiflow.forum", lastModified: new Date(), changeFrequency: "weekly", priority: 1 }]; }
