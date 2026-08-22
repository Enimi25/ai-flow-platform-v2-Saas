import { followUpEmail } from "../lib/email/follow-up";
import { STEPS } from "../lib/email/sequence";
import { writeFileSync } from "node:fs";

const parts = STEPS.map(({ day, step }) => {
  const html = followUpEmail({
    step, name: "Марк",
    business: "Салон Аврора, парикмахерская на Тверской.",
    siteUrl: "https://aiflow.forum", contactEmail: "baskinltd@yahoo.com",
  });
  console.log(`  день ${String(day).padStart(2)} · ${step.padEnd(10)} ${Math.round(html.length / 1024)}КБ`);
  return `<div style="padding:20px;background:#222"><div style="color:#9aa;font:600 12px sans-serif;letter-spacing:.1em;text-transform:uppercase;padding-bottom:10px">День ${day} · ${step}</div>${html}</div>`;
});

writeFileSync(
  "/private/tmp/claude-501/-Users-marcbaskin-Documents-claude/08358fcb-9dea-4f7c-a5ac-e9183074054f/scratchpad/sequence.html",
  `<meta charset="utf-8"><body style="margin:0;background:#111">${parts.join("")}</body>`,
);
console.log("\n  все четыре письма собраны");
