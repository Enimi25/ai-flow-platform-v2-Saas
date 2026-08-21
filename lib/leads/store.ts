import path from "node:path";
import { withFileLock, readJson, writeJson } from "@/lib/json-store";
import { safeRecord } from "@/lib/activity";

export type LeadStatus = "new" | "in_progress" | "converted" | "lost";
export const SOURCES = ["website", "facebook", "instagram", "whatsapp", "demo"] as const;
export type Source = (typeof SOURCES)[number];

export type Lead = {
  id: string;
  companyId: string;
  name: string;
  email: string;
  phone: string;
  source: Source;
  message: string;
  status: LeadStatus;
  createdAt: string;
};

const FILE = path.join(process.cwd(), ".data", "leads.json");

const readAll = () => readJson<Lead[]>(FILE, []);

const writeAll = (items: Lead[]) => writeJson(FILE, items);

export async function listLeads(companyId: string) {
  return (await readAll())
    .filter((lead) => lead.companyId === companyId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function saveLead(lead: Lead) {
  // saveLead
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const index = all.findIndex((entry) => entry.id === lead.id);
  if (index === -1) all.unshift(lead);
  else all[index] = lead;
  await writeAll(all);
  return lead;
  });
}

export function setStatus(id: string, status: LeadStatus) {
  // setStatus
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const lead = all.find((entry) => entry.id === id);
  if (!lead) return null;
  lead.status = status;
  await writeAll(all);
  return lead;
  });
}

const EMAIL = /[\w.+-]+@[\w-]+\.[\w.-]+/;
const PHONE = /(\+?\d[\d\s().-]{7,}\d)/;

/**
 * Pulls contact details out of what a visitor typed. A conversation that leaves
 * an email or a phone number is a lead, and losing it is the one failure the
 * product cannot afford.
 */
export function detectContact(text: string) {
  const email = text.match(EMAIL)?.[0] ?? "";
  const phone = text.match(PHONE)?.[0]?.trim() ?? "";
  return { email, phone, found: Boolean(email || phone) };
}

/** Same person, same conversation: update rather than pile up duplicates. */
export function captureLead(input: {
  companyId: string;
  email?: string;
  phone?: string;
  name?: string;
  message: string;
  source: Source;
}) {
  // captureLead
  return withFileLock(FILE, async () => {
  const all = await readAll();
  const match = all.find(
    (lead) =>
      lead.companyId === input.companyId &&
      ((input.email && lead.email === input.email) || (input.phone && lead.phone === input.phone)),
  );

  if (match) {
    match.message = `${match.message}\n${input.message}`.slice(-2000);
    if (input.name && !match.name) match.name = input.name;
    if (input.email && !match.email) match.email = input.email;
    if (input.phone && !match.phone) match.phone = input.phone;
    await writeAll(all);
    return { lead: match, isNew: false };
  }

  const lead: Lead = {
    id: crypto.randomUUID(),
    companyId: input.companyId,
    name: input.name?.slice(0, 120) ?? "",
    email: input.email?.slice(0, 254) ?? "",
    phone: input.phone?.slice(0, 40) ?? "",
    source: input.source,
    message: input.message.slice(0, 2000),
    status: "new",
    createdAt: new Date().toISOString(),
  };
  all.unshift(lead);
  await writeAll(all);

  safeRecord({
    companyId: input.companyId,
    kind: "lead.captured",
    level: "success",
    title: `New lead from ${input.source}`,
    detail: [lead.name, lead.email, lead.phone].filter(Boolean).join(" · ") || undefined,
  });

  return { lead, isNew: true };
  });
}
