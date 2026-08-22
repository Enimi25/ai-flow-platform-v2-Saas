/**
 * Starts the publishing loop when the server boots, so a scheduled post goes
 * out on its own without anything external having to poke the app.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const globalKey = Symbol.for("ai-flow.scheduler");
  const store = globalThis as unknown as Record<symbol, NodeJS.Timeout | undefined>;
  if (store[globalKey]) return;

  const { runDue } = await import("@/lib/content/runner");
  const { releaseExpired } = await import("@/lib/booking/store");
  const { runAutopilot } = await import("@/lib/content/autopilot");
  const { seedHouseWorkspace } = await import("@/lib/workspace/seed");
  const { runSequence } = await import("@/lib/email/sequence");

  if (await seedHouseWorkspace().catch(() => false)) {
    console.log("[scheduler] described AI FLOW to its own agent");
  }

  const tick = async () => {
    // top the queues up before publishing, so a fresh workspace is not idle
    const filled = await runAutopilot().catch(() => null);
    if (filled?.queued) console.log(`[scheduler] queued ${filled.queued} new posts`);

    const mailed = await runSequence().catch(() => null);
    if (mailed?.sent) console.log(`[scheduler] sent ${mailed.sent} follow ups`);

    try {
      const result = await runDue();
      if (result.picked) {
        console.log(`[scheduler] published ${result.published}, failed ${result.failed}`);
      }
      await releaseExpired();
    } catch (error) {
      console.error("[scheduler]", error);
    }
  };

  store[globalKey] = setInterval(tick, 60_000);
  void tick();
  console.log("[scheduler] running, checking every 60s");
}
