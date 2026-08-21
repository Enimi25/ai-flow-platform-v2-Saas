/**
 * Reading Latin-script Russian aloud.
 *
 * Half the messages this widget sees are Russian typed on a Latin keyboard —
 * "privet, kak dela". Handed to an English voice that comes out as nonsense
 * syllables, and handed to a Russian voice it is worse. The fix is to notice
 * the transliteration and turn it back into Cyrillic before speaking.
 */

/** Words that are common in Russian and near-absent in Latin-script languages. */
const RU_WORDS = new RegExp(
  "\\b(" +
    [
      "privet", "spasibo", "pozhaluista", "pozhalusta", "zdravstvui\\w*",
      "kak", "chto", "shto", "eto", "etot", "eta", "eti", "nado", "nuzhno", "nuzhen",
      "mozhno", "mozhesh", "mozhem", "davai", "davaite", "horosho", "khorosho",
      "hochu", "khochu", "tebe", "tebya", "menya", "mne", "moi", "moya", "tvoi",
      "nas", "vas", "oni", "seichas", "poka", "esche", "eshche", "ochen",
      "tolko", "tol", "budet", "byl", "byla", "esli", "kogda", "gde", "kto",
      "pochemu", "zachem", "vse", "vsyo", "sdelai", "sdelat", "delat", "delaet",
      "rabota\\w*", "posmotri", "skazhi", "znayu", "dumayu", "nemnogo",
      "ochered", "voprosy?", "otvet\\w*", "klient\\w*", "saity?", "web",
      "prosto", "luchshe", "bolshe", "menshe", "pervy\\w*", "novy\\w*",
      "nichego", "vsegda", "nikogda", "konechno", "navernoe", "znachit",
      "vot", "taki[ey]?", "takaya", "kotory[ei]", "kotoraya", "kotorye",
      "govorit", "govorish", "dolzh[ea]n", "dolzhna", "dolzhno", "budesh",
      "sdelal", "mozhet", "nravitsya", "cvet\\w*", "dizain\\w*", "okno",
      "knopk\\w*", "stronic\\w*", "zdes", "tam", "tut", "uzhe", "esli",
    ].join("|") +
    ")\\b",
  "gi",
);

/** Latin stopwords that would rule the guess out. */
const EN_WORDS =
  /\b(the|and|for|are|with|that|this|from|have|your|you|our|about|will|would|can|not|but|all|how|what|when|where|who|why|it's|its|been|more|than|then|they|their)\b/gi;

const DIGRAPHS = /(zh|kh|shch|sch|ts|ya|yu|yo|ch|sh|ye)/gi;

/** True when Latin text is more plausibly Russian than English. */
export function isTranslitRussian(text: string) {
  const latin = text.replace(/[^A-Za-z' ]/g, " ");
  const words = latin.split(/\s+/).filter((w) => w.length > 1);
  if (words.length < 2) return false;

  const ru = (latin.match(RU_WORDS) ?? []).length;
  const en = (latin.match(EN_WORDS) ?? []).length;
  const digraphs = (latin.match(DIGRAPHS) ?? []).length;

  if (en > ru) return false;
  if (ru >= 2) return true;
  if (ru >= 1 && en === 0 && words.length >= 3) return true;
  return digraphs / words.length > 0.3;
}

// Longest first, or "sh" would eat the "s" of "shch".
const PAIRS: [string, string][] = [
  ["shch", "щ"], ["sch", "щ"], ["yo", "ё"], ["jo", "ё"], ["zh", "ж"], ["kh", "х"],
  ["ts", "ц"], ["ch", "ч"], ["sh", "ш"], ["yu", "ю"], ["ju", "ю"], ["ya", "я"],
  ["ja", "я"], ["je", "е"], ["yi", "ый"], ["ii", "ий"],
  ["a", "а"], ["b", "б"], ["v", "в"], ["g", "г"], ["d", "д"], ["e", "е"],
  ["z", "з"], ["i", "и"], ["k", "к"], ["l", "л"], ["m", "м"], ["n", "н"],
  ["o", "о"], ["p", "п"], ["r", "р"], ["s", "с"], ["t", "т"], ["u", "у"],
  ["f", "ф"], ["h", "х"], ["c", "ц"], ["y", "ы"], ["j", "й"], ["q", "к"],
  ["w", "в"], ["x", "кс"], ["'", "ь"],
];

/**
 * People drop the soft sign when they type Russian in Latin — "bolshe", not
 * "bol'she". Putting the apostrophes back before conversion is cheaper than
 * teaching the mapping about them, since ' already maps to ь.
 */
const SOFTEN: [RegExp, string][] = [
  [/\b(bol|tol|skol|nachal|kotor)(sh|k)/gi, "$1'$2"],
  [/(\w)(esh|ish)\b/gi, "$1$2'"],
  [/(\w)lis\b/gi, "$1lis'"],
  [/\b(ochen|teper|zdes|opyat|tolko|skolko|dolzhen|den|mat|pyat|shest|sem|vosem|ves|ves)\b/gi, "$1'"],
  [/t(sya)\b/gi, "t'$1"],
  [/ct/gi, "kt"],
];

/** Latin-script Russian back into Cyrillic, well enough to be read aloud. */
export function toCyrillic(text: string) {
  for (const [pattern, into] of SOFTEN) text = text.replace(pattern, into);
  // A trailing i after a vowel is the short й: davai, moi, tvoi.
  let out = text.replace(/([aoue])i\b/gi, "$1y_SHORT_");
  // ye is е only where a Russian word would carry it — at the start, or after
  // a vowel. Inside a word it is nearly always ы + е, as in dannye.
  out = out.replace(/\bye/gi, "_YE_").replace(/([aeiouy])ye/gi, "$1_YE_");
  // and the handful of words that open on э rather than е
  out = out.replace(/\bet(o|ot|a|i|im|om|ogo)\b/gi, (m) => "_E_" + m.slice(1));

  const lower = out.toLowerCase();
  let result = "";
  let index = 0;

  while (index < lower.length) {
    if (lower.startsWith("y_short_", index)) {
      result += "й";
      index += 8;
      continue;
    }
    if (lower.startsWith("_ye_", index)) {
      result += "е";
      index += 4;
      continue;
    }
    if (lower.startsWith("_e_", index)) {
      result += "э";
      index += 3;
      continue;
    }
    const hit = PAIRS.find(([latin]) => lower.startsWith(latin, index));
    if (hit) {
      result += hit[1];
      index += hit[0].length;
    } else {
      result += out[index];
      index += 1;
    }
  }

  out = result;
  return out;
}
