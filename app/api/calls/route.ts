import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { listCalls, saveCall, getCall, callStats, alreadyQueued, isOutcome } from "@/lib/calls/store";
import { writeScript } from "@/lib/calls/script";
import { listLeads, setStatus } from "@/lib/leads/store";
import { isTelephonyReady, providerStatus } from "@/lib/calls/provider";
import { safeRecord } from "@/lib/activity";
import type { Call } from "@/lib/calls/types";

export async function GET() {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const [calls, stats, leads] = await Promise.all([
    listCalls(companyId),
    callStats(companyId),
    listLeads(companyId),
  ]);

  // leads worth calling: they left a number and nobody has queued them yet
  const queueable = [];
  for (const lead of leads) {
    if (!lead.phone || lead.status === "converted" || lead.status === "lost") continue;
    if (await alreadyQueued(companyId, lead.phone)) continue;
    queueable.push({
      id: lead.id,
      name: lead.name || "",
      phone: lead.phone,
      source: lead.source,
      message: (lead.message || "").slice(0, 160),
      createdAt: lead.createdAt,
    });
  }

  return NextResponse.json({
    calls,
    stats,
    queueable: queueable.slice(0, 40),
    telephony: { ready: isTelephonyReady(), ...providerStatus() },
  });
}

export async function POST(request: Request) {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const phone = typeof body.phone === "string" ? body.phone.trim().slice(0, 40) : "";
  if (!phone) return NextResponse.json({ error: "A call needs a phone number." }, { status: 422 });

  if (await alreadyQueued(companyId, phone)) {
    return NextResponse.json({ error: "That number is already in the queue." }, { status: 409 });
  }

  const call: Call = {
    id: crypto.randomUUID(),
    companyId,
    leadId: typeof body.leadId === "string" ? body.leadId : undefined,
    name: typeof body.name === "string" ? body.name.slice(0, 120) : "",
    phone,
    reason: typeof body.reason === "string" ? body.reason.slice(0, 300) : "Left a phone number and no one has called back.",
    context: typeof body.context === "string" ? body.context.slice(0, 600) : "",
    status: "queued",
    attempts: 0,
    dueAt: typeof body.dueAt === "string" ? body.dueAt : new Date().toISOString(),
    createdAt: new Date().toISOString(),
  };

  await saveCall(call);
  return NextResponse.json({ call }, { status: 201 });
}

export async function PATCH(request: Request) {
  const session = await getSession();
  const companyId = session?.companyId;
  if (!companyId) return NextResponse.json({ error: "Sign in first." }, { status: 401 });

  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const id = typeof body.id === "string" ? body.id : "";
  const call = id ? await getCall(id) : null;
  if (!call || call.companyId !== companyId) {
    return NextResponse.json({ error: "No such call." }, { status: 404 });
  }

  // ask the model for a brief on this one person
  if (body.action === "script") {
    const script = await writeScript({
      companyId,
      name: call.name,
      reason: call.reason,
      visitorId: call.leadId,
    }).catch(() => null);
    if (!script) return NextResponse.json({ error: "Could not write the brief. Try again." }, { status: 503 });
    return NextResponse.json({ call: await saveCall({ ...call, script }) });
  }

  if (body.action === "outcome") {
    if (!isOutcome(body.outcome)) return NextResponse.json({ error: "Unknown outcome." }, { status: 422 });

    const callbackAt = typeof body.dueAt === "string" ? body.dueAt : null;
    const settled: Call = {
      ...call,
      attempts: call.attempts + 1,
      notes: typeof body.notes === "string" ? body.notes.slice(0, 1_000) : call.notes,
      outcome: body.outcome,
      // a promised callback goes back into the queue rather than being closed
      status: body.outcome === "callback" || body.outcome === "no_answer" ? "queued" : "done",
      dueAt: callbackAt ?? call.dueAt,
      completedAt: body.outcome === "callback" || body.outcome === "no_answer" ? undefined : new Date().toISOString(),
    };
    await saveCall(settled);

    if (call.leadId) {
      const status =
        body.outcome === "booked" ? "converted" : body.outcome === "not_interested" ? "lost" : "in_progress";
      await setStatus(call.leadId, status).catch(() => {});
    }

    safeRecord({
      companyId,
      kind: "call.logged",
      level: body.outcome === "booked" ? "success" : "info",
      title: `Call logged: ${body.outcome.replace("_", " ")}`,
      detail: `${call.name || call.phone}`,
    });

    return NextResponse.json({ call: settled });
  }

  return NextResponse.json({ error: "Unknown action." }, { status: 422 });
}
