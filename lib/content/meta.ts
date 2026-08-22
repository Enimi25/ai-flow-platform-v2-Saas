import { saveConnection } from "@/lib/content/connections";

const GRAPH = "https://graph.facebook.com/v21.0";

type Page = {
  id: string;
  name: string;
  access_token: string;
  instagram_business_account?: { id: string; username?: string };
};

export async function connectMetaAccounts(companyId: string, accessToken: string) {
  const url = new URL(`${GRAPH}/me/accounts`);
  url.searchParams.set("fields", "id,name,access_token,instagram_business_account{id,username}");
  url.searchParams.set("access_token", accessToken);

  const response = await fetch(url, { cache: "no-store" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(payload?.error?.message ?? "Facebook refused that login.");

  const page = (payload?.data ?? [])[0] as Page | undefined;
  if (!page) throw new Error("This Facebook account has no Page you can manage.");

  const pageToken = page.access_token || accessToken;
  await saveConnection({ companyId, channel: "facebook", accountId: page.id, accessToken: pageToken, accountName: page.name });

  const connected = [{ channel: "facebook", account: page.name }];
  const instagram = page.instagram_business_account;
  if (instagram?.id) {
    await saveConnection({
      companyId,
      channel: "instagram",
      accountId: instagram.id,
      accessToken: pageToken,
      accountName: instagram.username ? `@${instagram.username}` : page.name,
    });
    connected.push({ channel: "instagram", account: instagram.username ?? instagram.id });
  }

  return connected;
}
