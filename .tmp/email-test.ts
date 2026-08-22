import { previewConversation } from "../lib/email/preview";
import { proposalEmail } from "../lib/email/proposal";
import { writeFileSync } from "node:fs";

async function main() {
  const business = "Салон Аврора, парикмахерская на Тверской 12 в Москве. Стрижка 2500 руб, окрашивание от 6000 руб. Работаем вторник-воскресенье с 10 до 20, понедельник выходной.";
  const preview = await previewConversation(business);
  console.log("сгенерировано обменов:", preview.length);
  for (const p of preview) {
    console.log("\n  клиент: " + p.asked);
    console.log("  агент:  " + p.answered);
  }
  const html = proposalEmail({
    name: "Марк", question: business, preview,
    siteUrl: "https://aiflow.forum", contactEmail: "baskinltd@yahoo.com",
  });
  writeFileSync("/private/tmp/claude-501/-Users-marcbaskin-Documents-claude/08358fcb-9dea-4f7c-a5ac-e9183074054f/scratchpad/proposal.html", html);
  console.log("\nписьмо сохранено, " + Math.round(html.length / 1024) + "КБ");
}
main();
