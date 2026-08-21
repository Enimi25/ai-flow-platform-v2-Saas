import { promises as fs } from "node:fs";
import path from "node:path";

export type Workspace = {
  companyId: string;
  ownerEmail: string;
  name: string;
  createdAt: string;
};

const FILE = path.join(process.cwd(), ".data", "workspaces.json");

async function readAll(): Promise<Record<string, Workspace>> {
  try {
    return JSON.parse(await fs.readFile(FILE, "utf8"));
  } catch {
    return {};
  }
}

/** Stable, readable, and safe to paste into a widget snippet. */
function slugFor(email: string) {
  const base = (email.split("@")[1]?.split(".")[0] || email.split("@")[0] || "workspace")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 24) || "workspace";
  return `${base}-${crypto.randomUUID().slice(0, 6)}`;
}

/**
 * Every account that signs in gets its own workspace on first sight, so leads,
 * bookings and the widget snippet are never shared between customers.
 */
export async function workspaceFor(email: string): Promise<Workspace> {
  const all = await readAll();
  const existing = Object.values(all).find((workspace) => workspace.ownerEmail === email);
  if (existing) return existing;

  const workspace: Workspace = {
    companyId: slugFor(email),
    ownerEmail: email,
    name: email.split("@")[0],
    createdAt: new Date().toISOString(),
  };
  all[workspace.companyId] = workspace;
  await fs.mkdir(path.dirname(FILE), { recursive: true });
  await fs.writeFile(FILE, JSON.stringify(all, null, 2), "utf8");
  return workspace;
}

/**
 * The workspace that owns aiflow.forum itself.
 *
 * Leads from our own landing page and demo form used to be filed under a
 * literal "preview", which no account owns — so they were invisible to the one
 * person who needed to see them. They belong to whoever runs the platform,
 * which is the first account created.
 */
export async function houseCompanyId() {
  const all = Object.values(await readAll());
  if (!all.length) return "preview";
  const oldest = all.sort((a, b) => a.createdAt.localeCompare(b.createdAt))[0];
  return oldest.companyId;
}

export async function workspaceById(companyId: string) {
  return (await readAll())[companyId] ?? null;
}
