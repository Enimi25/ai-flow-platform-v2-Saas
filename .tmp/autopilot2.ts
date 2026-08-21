import { runAutopilot } from "../lib/content/autopilot";
import { listPosts } from "../lib/content/store";
async function main() {
  const id = "stomatologiya-a882f6";
  // сбрасываю таймер, чтобы прогнать сразу
  const result = await runAutopilot(Date.now() + 7 * 60 * 60 * 1000);
  console.log("автопилот:", result);
  const posts = await listPosts(id);
  console.log("постов:", posts.length);
  const msk = (iso: string) => new Date(iso).toLocaleString("ru-RU", { timeZone: "Europe/Moscow", dateStyle: "short", timeStyle: "short" });
  for (const p of posts) console.log("  ", msk(p.scheduledAt), "МСК |", p.channel, "|", p.body.slice(0, 70).replace(/\n/g, " "));
}
main();
