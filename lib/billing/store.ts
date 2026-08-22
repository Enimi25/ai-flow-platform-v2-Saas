import path from "node:path";
import { readJson, withFileLock, writeJson } from "@/lib/json-store";

export type Subscription = {
  companyId: string;
  planId: string;
  stripeCustomerId?: string;
  stripeSubscriptionId: string;
  status: string;
  updatedAt: string;
};

const FILE = path.join(process.cwd(), ".data", "subscriptions.json");

export async function subscriptionFor(companyId: string) {
  return (await readJson<Subscription[]>(FILE, [])).find((subscription) => subscription.companyId === companyId) ?? null;
}

export function saveSubscription(subscription: Subscription) {
  return withFileLock(FILE, async () => {
    const all = await readJson<Subscription[]>(FILE, []);
    const index = all.findIndex((entry) => entry.companyId === subscription.companyId);
    if (index === -1) all.push(subscription);
    else all[index] = subscription;
    await writeJson(FILE, all);
    return subscription;
  });
}
