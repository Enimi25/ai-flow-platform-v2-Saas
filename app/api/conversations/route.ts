import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listConversations } from "@/lib/conversations/store";

export async function GET() {
  const session = await getSession();
  const threads = await listConversations(session?.companyId ?? "preview");
  return NextResponse.json({
    threads,
    total: threads.length,
    withLead: threads.filter((thread) => thread.leadId).length,
  });
}
