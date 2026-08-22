import { answerLanguage } from "../lib/language";
const cases: [string, string][] = [
  ["Dadite skidku 70%? Inache uidu k konkurentam", "Russian"],
  ["privet kak dela", "Russian"],
  ["hochu zapisatsya na strizhku", "Russian"],
  ["skolko stoit chistka zubov", "Russian"],
  ["kuda popadayut dannye moih klientov", "Russian"],
  ["vy rabotaete v voskresene", "Russian"],
  ["Can you give me a discount of 70 percent", "English"],
  ["Do you work on sundays and what does it cost", "English"],
  ["How much is a cleaning and can I book today", "English"],
  ["Сколько стоит стрижка", "Russian"],
  ["Hola, cuanto cuesta el servicio para mi empresa", "Spanish"],
];
let bad = 0;
for (const [text, want] of cases) {
  const got = answerLanguage(text);
  const ok = got.startsWith(want);
  if (!ok) bad++;
  console.log(`  ${ok ? "OK  " : "МИМО"} ${want.padEnd(8)} -> ${got.padEnd(28)} ${text.slice(0, 46)}`);
}
console.log(bad ? `\n  промахов: ${bad}` : "\n  все верно");
