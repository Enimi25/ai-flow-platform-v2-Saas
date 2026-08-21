import { runAutopilot } from "../lib/content/autopilot";
import { listPosts } from "../lib/content/store";
import { saveConnection } from "../lib/content/connections";
import { getSettings, saveSettings } from "../lib/settings/store";

async function main() {
  const id = "stomatologiya-a882f6";

  // клиника подключает Facebook и включает автопилот
  await saveConnection({
    companyId: id, channel: "facebook",
    accountId: "111222333", accessToken: "test-token-nikuda-ne-uidet",
    accountName: "Белый Клык",
  });
  const s = await getSettings(id);
  await saveSettings({ ...s, contentAuto: true, contentPerWeek: 3 });

  console.log("до:", (await listPosts(id)).length, "постов");
  const result = await runAutopilot(Date.now());
  console.log("автопилот:", result);

  const posts = await listPosts(id);
  console.log("после:", posts.length, "постов\n");
  for (const p of posts.slice(0, 4)) {
    console.log(" ", p.scheduledAt.slice(0, 16).replace("T", " "), "|", p.channel, "|", p.body.slice(0, 90).replace(/\n/g, " "));
  }
}
main();
