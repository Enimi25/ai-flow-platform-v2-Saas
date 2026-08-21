import { isTranslitRussian, toCyrillic } from "../components/translit";
const cases = [
  "privet kak dela",
  "davai sdelaem eto segodnya",
  "ya hochu chto by dannye sohranyalis",
  "posmotri video i skazhi chto dumaesh",
  "vot takoi avatar nado interactivnyi kotoryi govorit",
  "The assistant answers in seconds and books the appointment",
  "Our pricing starts at 49 a month for the starter plan",
  "spasibo bolshoe vsyo rabotaet horosho",
];
for (const c of cases) {
  const ru = isTranslitRussian(c);
  console.log((ru ? "RU  " : "EN  ") + c + (ru ? "\n     -> " + toCyrillic(c) : ""));
}
