import { promises as fs } from "node:fs";
import path from "node:path";
import { seal, open } from "@/lib/google/crypto";
import { CHANNELS } from "./types";
import { dataFile } from "@/lib/data-dir";

/** WhatsApp is a messaging connection, not a publishing channel. */
export const CONNECTION_CHANNELS = [...CHANNELS, "whatsapp"] as const;
export type ConnectionChannel = (typeof CONNECTION_CHANNELS)[number];

export type Connection = {
  companyId: string;
  channel: ConnectionChannel;
  /** Page id, IG user id, or the TikTok open id, depending on the channel. */
  accountId: string;
  accessToken: string;
  accountName?: string;
  connectedAt: string;
};

const FILE = dataFile("connections.json");
const key = (companyId: string, channel: ConnectionChannel) => `${companyId}:${channel}`;

async function readAll(): Promise<Record<string, Connection>> {
  try {
    return JSON.parse(await fs.readFile(FILE, "utf8"));
  } catch {
    return {};
  }
}

export async function saveConnection(input: Omit<Connection, "connectedAt">) {
  const all = await readAll();
  all[key(input.companyId, input.channel)] = {
    ...input,
    accessToken: seal(input.accessToken),
    connectedAt: new Date().toISOString(),
  };
  await fs.mkdir(path.dirname(FILE), { recursive: true });
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
}

export async function removeConnection(companyId: string, channel: ConnectionChannel) {
  const all = await readAll();
  delete all[key(companyId, channel)];
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
}

/**
 * A workspace's own account first. The platform's env credentials are the
 * fallback, which is what AI FLOW itself posts through.
 */
export async function connectionFor(companyId: string, channel: ConnectionChannel) {
  const stored = (await readAll())[key(companyId, channel)];
  if (stored) {
    return {
      accountId: stored.accountId,
      accessToken: open(stored.accessToken),
      accountName: stored.accountName,
      own: true as const,
    };
  }

  const fallback: Record<ConnectionChannel, { id?: string; token?: string }> = {
    facebook: { id: process.env.FACEBOOK_PAGE_ID, token: process.env.FACEBOOK_PAGE_ACCESS_TOKEN },
    instagram: { id: process.env.INSTAGRAM_USER_ID, token: process.env.FACEBOOK_PAGE_ACCESS_TOKEN },
    tiktok: { id: process.env.TIKTOK_OPEN_ID, token: process.env.TIKTOK_ACCESS_TOKEN },
    whatsapp: { id: process.env.WHATSAPP_PHONE_NUMBER_ID, token: process.env.WHATSAPP_ACCESS_TOKEN },
  };

  const entry = fallback[channel];
  if (!entry.token) return null;
  return { accountId: entry.id ?? "", accessToken: entry.token, accountName: undefined, own: false as const };
}

/**
 * Which workspace owns a Page or Instagram account.
 *
 * Meta's webhook names the account, not the customer, so an inbound message can
 * only be routed by walking the connections back to whoever linked it.
 */
export async function connectionByAccount(accountId: string, channel?: ConnectionChannel) {
  const all = await readAll();
  for (const entry of Object.values(all)) {
    if (entry.accountId !== accountId) continue;
    if (channel && entry.channel !== channel) continue;
    return { ...entry, accessToken: open(entry.accessToken) };
  }
  return null;
}

export async function connectionsFor(companyId: string) {
  const all = await readAll();
  return CONNECTION_CHANNELS.map((channel) => {
    const stored = all[key(companyId, channel)];
    return {
      channel,
      connected: Boolean(stored),
      accountName: stored?.accountName ?? null,
      connectedAt: stored?.connectedAt ?? null,
    };
  });
}
