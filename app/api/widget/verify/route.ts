import { NextResponse } from "next/server";
import { promises as fs } from "node:fs";
import path from "node:path";
import { getSession } from "@/lib/session";

const FILE = path.join(process.cwd(), ".data", "widget-installs.json");

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  try {
    const all = JSON.parse(await fs.readFile(FILE, "utf8")) as Record<
      string,
      { hosts: string[]; lastSeen: string }
    >;
    const entry = all[companyId];
    return NextResponse.json({
      installed: Boolean(entry?.hosts.length),
      hosts: entry?.hosts ?? [],
      lastSeen: entry?.lastSeen ?? null,
    });
  } catch {
    return NextResponse.json({ installed: false, hosts: [], lastSeen: null });
  }
}
