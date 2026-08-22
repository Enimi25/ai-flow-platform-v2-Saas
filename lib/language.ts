import { isTranslitRussian } from "@/components/translit";

/**
 * Which language to answer in, decided here rather than left to the model.
 *
 * Asked in Latin-script Russian for a discount, the agent replied in Ukrainian:
 * the model saw a Slavic language in Latin letters and guessed. Guessing wrong
 * in front of a customer is worse than most bugs, so the prompt is told the
 * answer instead of being invited to work it out.
 */
const SCRIPTS: [RegExp, string][] = [
  [/[\u0400-\u04FF]/, "Russian"],
  [/[\u0370-\u03ff]/, "Greek"],
  [/[\u0590-\u05ff]/, "Hebrew"],
  [/[\u0600-\u06ff]/, "Arabic"],
  [/[\u0e00-\u0e7f]/, "Thai"],
  [/[\uac00-\ud7af]/, "Korean"],
  [/[\u3040-\u30ff]/, "Japanese"],
  [/[\u4e00-\u9fff]/, "Chinese"],
];

const LATIN: [RegExp, string][] = [
  [/\b(el|la|los|que|para|con|una|pero|como|muy|gracias|hola)\b/i, "Spanish"],
  [/\b(le|les|des|une|pour|avec|vous|nous|merci|bonjour)\b/i, "French"],
  [/\b(der|die|das|und|nicht|mit|f\u00fcr|ist|danke|hallo)\b/i, "German"],
  [/\b(il|gli|che|per|con|una|sono|grazie|ciao)\b/i, "Italian"],
];

export function answerLanguage(text: string) {
  for (const [pattern, name] of SCRIPTS) if (pattern.test(text)) return name;
  // Latin-script Russian: the customer types privet, the answer is Cyrillic
  if (isTranslitRussian(text)) return "Russian, written in Cyrillic";
  for (const [pattern, name] of LATIN) if (pattern.test(text)) return name;
  return "English";
}
