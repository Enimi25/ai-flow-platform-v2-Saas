import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listConversations } from "@/lib/conversations/store";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const threads = await listConversations(companyId);
  return NextResponse.json({
    threads,
    total: threads.length,
    withLead: threads.filter((thread) => thread.leadId).length,
  });
}
