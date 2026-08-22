"use client";

import { isTranslitRussian, toCyrillic } from "./translit";

/** Scripts that identify a language on sight. */
const SCRIPTS: [RegExp, string][] = [
  [/[Ѐ-ӿ]/, "ru-RU"],
  [/[\u0370-\u03ff]/, "el-GR"],
  [/[\u0590-\u05ff]/, "he-IL"],
  [/[\u0600-\u06ff]/, "ar-SA"],
  [/[\u0900-\u097f]/, "hi-IN"],
  [/[\u0e00-\u0e7f]/, "th-TH"],
  [/[\uac00-\ud7af]/, "ko-KR"],
  [/[\u3040-\u30ff]/, "ja-JP"],
  [/[\u4e00-\u9fff]/, "zh-CN"],
];

/** Latin languages, told apart by the words only they use. */
const LATIN: [RegExp, string][] = [
  [/\b(el|la|los|las|que|para|con|una|pero|como|muy|está|más|gracias)\b/gi, "es-ES"],
  [/\b(le|les|des|une|pour|avec|vous|nous|est|être|merci|c'est|dans)\b/gi, "fr-FR"],
  [/\b(der|die|das|und|nicht|mit|für|ist|sie|auch|aber|danke|sehr)\b/gi, "de-DE"],
  [/\b(il|lo|gli|che|per|con|una|sono|questo|grazie|molto|anche)\b/gi, "it-IT"],
  [/\b(o|os|as|não|para|com|uma|muito|obrigad[oa]|você|está)\b/gi, "pt-PT"],
  [/\b(nie|jest|się|dla|tego|bardzo|dziękuję|czy|jak)\b/gi, "pl-PL"],
  [/\b(bir|için|çok|ve|bu|ne|nasıl|teşekkür)\b/gi, "tr-TR"],
];

/**
 * The language of a piece of text, and the text as it should be handed to the
 * synthesiser. Latin-script Russian comes back converted to Cyrillic: read as
 * written it is gibberish in any voice.
 */
export function langOf(text: string): { lang: string; speak: string } {
  for (const [pattern, lang] of SCRIPTS) {
    if (pattern.test(text)) return { lang, speak: text };
  }
  if (isTranslitRussian(text)) return { lang: "ru-RU", speak: toCyrillic(text) };

  let best = { lang: "en-US", hits: 0 };
  for (const [pattern, lang] of LATIN) {
    const hits = (text.match(pattern) ?? []).length;
    if (hits > best.hits) best = { lang, hits };
  }
  return { lang: best.lang, speak: text };
}

let cache: SpeechSynthesisVoice[] = [];

/** getVoices() is empty on first call in every browser but Safari. */
export function warmVoices() {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  const read = () => {
    cache = window.speechSynthesis.getVoices();
  };
  read();
  window.speechSynthesis.addEventListener("voiceschanged", read);
}

/**
 * macOS ships a pile of novelty voices — Zarvox, Trinoids, Bubbles — and one of
 * them being first in the list is most of why browser speech sounds like a
 * robot. Rank instead of taking the default.
 */
const NOVELTY =
  /albert|bad news|bahh|bells|boing|bubbles|cellos|deranged|deranged|good news|jester|junior|organ|ralph|superstar|trinoids|whisper|wobble|zarvox|hysterical|pipe|grandma|grandpa|rocko|shelley|sandy|eddy|flo|reed|fred|kathy|princess|bruce|agnes|victoria/i;

/** Named voices that actually sound like a person, best first. */
const FAVOURED: Record<string, RegExp> = {
  en: /ava|allison|samantha|serena|zoe|evan|nathan|jenny|aria|libby|natural|neural/i,
  ru: /milena|katya|yuri|dariya|svetlana|natural|neural/i,
};

function pickVoice(lang: string) {
  if (!cache.length) cache = window.speechSynthesis.getVoices();
  const tag = lang.toLowerCase();
  const root = tag.slice(0, 2);
  const norm = (v: SpeechSynthesisVoice) => v.lang.replace("_", "-").toLowerCase();

  const family = cache.filter((v) => norm(v).startsWith(root) && !NOVELTY.test(v.name));
  if (!family.length) return null;

  const favoured = FAVOURED[root];
  const score = (v: SpeechSynthesisVoice) => {
    let n = 0;
    if (favoured?.test(v.name)) n += 8;
    if (/premium|enhanced|natural|neural/i.test(v.name)) n += 6;
    // Chrome streams its Google voices from the network, and they are a clear
    // step above anything installed locally.
    if (!v.localService) n += 5;
    if (/google/i.test(v.name)) n += 4;
    if (/microsoft/i.test(v.name)) n += 2;
    if (norm(v) === tag) n += 2;
    if (v.default) n += 1;
    return n;
  };

  return [...family].sort((a, b) => score(b) - score(a))[0] ?? null;
}

/**
 * Long replies get cut off mid-sentence in Chrome — a decade-old bug in its
 * synthesiser. Splitting on sentence boundaries dodges it and keeps the
 * mascot's jaw moving across the whole answer rather than the first clause.
 */
function chunk(text: string) {
  return text
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?…])\s+/)
    .flatMap((piece) => (piece.length <= 180 ? [piece] : piece.match(/.{1,180}(\s|$)/g) ?? [piece]))
    .map((piece) => piece.trim())
    .filter(Boolean);
}

export type Speaking = { onStart?: () => void; onEnd?: () => void };

/** Speaks `text` aloud. Returns false when the browser has no synthesiser. */
export function say(text: string, { onStart, onEnd }: Speaking = {}) {
  if (typeof window === "undefined" || !window.speechSynthesis) return false;

  const synth = window.speechSynthesis;
  synth.cancel();

  const parts = chunk(text);
  if (!parts.length) return false;

  let started = false;
  parts.forEach((part, index) => {
    // per sentence, because a reply can switch language mid-answer
    const { lang, speak } = langOf(part);
    const voice = pickVoice(lang);
    const utterance = new SpeechSynthesisUtterance(speak);
    utterance.lang = lang;
    if (voice) utterance.voice = voice;
    // Flo is a puppy, so a touch brighter and a touch quicker than neutral.
    // Not higher: past about 1.2 the voice stops sounding young and starts
    // sounding synthetic, which is the thing this was meant to fix.
    utterance.rate = 1.04;
    utterance.pitch = 1.12;
    utterance.onstart = () => {
      if (started) return;
      started = true;
      onStart?.();
    };
    if (index === parts.length - 1) {
      utterance.onend = () => onEnd?.();
      utterance.onerror = () => onEnd?.();
    }
    synth.speak(utterance);
  });

  return true;
}

export function hush() {
  if (typeof window !== "undefined") window.speechSynthesis?.cancel();
}
