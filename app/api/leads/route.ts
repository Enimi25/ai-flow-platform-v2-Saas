import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listLeads, setStatus, captureLead, SOURCES, type Source, type LeadStatus } from "@/lib/leads/store";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const leads = await listLeads(companyId);
  const counts = leads.reduce<Record<string, number>>((totals, lead) => {
    totals[lead.status] = (totals[lead.status] ?? 0) + 1;
    return totals;
  }, {});
  return NextResponse.json({ leads, counts, total: leads.length });
}

export async function POST(request: Request) {
  const session = await getSession();
  const body = (await request.json().catch(() => ({}))) as Record<string, string>;

  if (!body.email && !body.phone) {
    return NextResponse.json({ error: "A lead needs an email or a phone number." }, { status: 400 });
  }

  const source: Source = SOURCES.includes(body.source as Source) ? (body.source as Source) : "website";
  const { lead, isNew } = await captureLead({
    companyId: body.companyId || session?.companyId || "preview",
    email: body.email,
    phone: body.phone,
    name: body.name,
    message: body.message ?? "",
    source,
  });

  return NextResponse.json({ lead, isNew }, { status: isNew ? 201 : 200 });
}

export async function PATCH(request: Request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const { id, status } = (await request.json().catch(() => ({}))) as { id?: string; status?: LeadStatus };
  if (!id || !status) return NextResponse.json({ error: "Need an id and a status." }, { status: 400 });

  const lead = await setStatus(id, status);
  if (!lead) return NextResponse.json({ error: "No such lead." }, { status: 404 });
  return NextResponse.json({ lead });
}
