/**
 * One way to ask a model anything, over a ladder of providers.
 *
 * The order comes from MODEL_PROVIDERS, so adding or reordering a provider is a
 * configuration change, never a code change. Each rung is tried until one
 * answers, which is why a decommissioned model or an expired key can no longer
 * leave a customer staring at silence.
 */

export type Weight = "light" | "heavy";

export type Ask = {
  system: string;
  user: string;
  temperature?: number;
  maxTokens?: number;
  /** "light" is enough for opening hours and prices. "heavy" earns the big model. */
  weight?: Weight;
};

export type Answer = {
  text: string;
  via: string;
  model: string;
  weight: Weight;
  /** True when every rung admitted it could not answer from what it was given. */
  unsure?: boolean;
};

/**
 * A model that cannot answer from what it was given says so with this marker
 * instead of guessing. The ladder treats that as a reason to climb, so a small
 * local model can take the easy questions and hand the rest upward.
 */
export const UNSURE = "[[UNSURE]]";

export const ESCALATION_RULE =
  `If the answer is not in the information above, reply with exactly ${UNSURE} and nothing else. Never guess.`;

class Escalate extends Error {
  constructor(readonly from: string) {
    super(`${from} was unsure`);
  }
}

export class NoModelAvailable extends Error {
  constructor(public readonly tried: string[]) {
    super(`No model answered. Tried: ${tried.join(" | ")}`);
    this.name = "NoModelAvailable";
  }
}

/* ── routing ─────────────────────────────────────────────────────────── */

// No \b around the Cyrillic stems: in JavaScript a word boundary is defined on
// ASCII, so \bсравн never matches and every Russian question looks simple.
const HARD_SIGNS = [
  /(сравн|разниц|почему|как именно|интеграц|подробн|отлича)/i,
  /(счёт|счет|договор|скидк|индивидуальн|под ключ|интегрир)/i,
  /\b(compare|difference|why|explain|integrat|custom|breakdown)/i,
];

/** Sorted locally, so routing costs no latency of its own. */
export function weigh(text: string): Weight {
  const trimmed = text.trim();
  if (trimmed.length > 180) return "heavy";
  if (trimmed.split(/[.!?]/).filter((part) => part.trim()).length > 2) return "heavy";
  if (HARD_SIGNS.some((sign) => sign.test(trimmed))) return "heavy";
  return "light";
}

/**
 * Models reach for typographic dashes and non breaking hyphens. They look wrong
 * in a chat bubble and break wrapping on a phone, so they are cleaned on the
 * way out rather than hoped for in the prompt.
 */
export function tidyText(text: string) {
  return text
    .replace(/[—–]/g, "-")
    .replace(/‑/g, "-")
    .replace(/ /g, " ")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/* ── providers ───────────────────────────────────────────────────────── */

type Provider = {
  id: string;
  ready: () => boolean;
  models: () => { light: string; heavy: string };
  run: (ask: Ask, model: string) => Promise<string>;
};

/** Anything that speaks the OpenAI chat shape: Groq, OpenRouter, Together, vLLM. */
function openAiCompatible(id: string, config: {
  url: string;
  key?: string;
  light?: string;
  heavy?: string;
  timeoutMs?: number;
  /** Some hosts rank and rate limit by the calling app, so they get named. */
  headers?: Record<string, string>;
}): Provider {
  return {
    id,
    ready: () => Boolean(config.key && config.heavy),
    models: () => ({ light: config.light || config.heavy || "", heavy: config.heavy || "" }),
    async run(ask, model) {
      const response = await fetch(config.url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${config.key}`,
          "Content-Type": "application/json",
          ...config.headers,
        },
        body: JSON.stringify({
          model,
          temperature: ask.temperature ?? 0.8,
          // Every current model reasons before answering. Left alone it either
          // spends the whole budget thinking and returns an empty string, or
          // leaks its <think> block into the customer's chat bubble.
          reasoning_format: "hidden",
          max_tokens: Math.max(ask.maxTokens ?? 1800, 400),
          messages: [
            { role: "system", content: ask.system },
            { role: "user", content: ask.user },
          ],
        }),
        signal: AbortSignal.timeout(config.timeoutMs ?? 45_000),
      });

      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.error?.message ?? `${id} ${response.status}`);
      const text = payload?.choices?.[0]?.message?.content;
      if (!text || !text.trim()) throw new Error(`${id} returned an empty answer`);
      if (text.includes("<think>")) throw new Error(`${id} leaked its reasoning`);
      return text;
    },
  };
}

/** Anthropic speaks its own shape: system is a top level field, not a message. */
const anthropic: Provider = {
  id: "anthropic",
  ready: () => Boolean(process.env.ANTHROPIC_API_KEY),
  models: () => ({
    light: process.env.ANTHROPIC_LIGHT_MODEL || "claude-haiku-4-5-20251001",
    heavy: process.env.ANTHROPIC_MODEL || "claude-sonnet-5",
  }),
  async run(ask, model) {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": process.env.ANTHROPIC_API_KEY as string,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        max_tokens: Math.max(ask.maxTokens ?? 1800, 400),
        temperature: ask.temperature ?? 0.8,
        system: ask.system,
        messages: [{ role: "user", content: ask.user }],
      }),
      signal: AbortSignal.timeout(60_000),
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(payload?.error?.message ?? `anthropic ${response.status}`);
    const text = (payload?.content ?? [])
      .filter((block: { type: string }) => block.type === "text")
      .map((block: { text: string }) => block.text)
      .join("");
    if (!text.trim()) throw new Error("anthropic returned an empty answer");
    return text;
  },
};

const OLLAMA_URL = process.env.OLLAMA_URL || "http://127.0.0.1:11434";
let localModelCache: { at: number; name: string | null } | null = null;

async function firstLocalModel(): Promise<string | null> {
  if (localModelCache && Date.now() - localModelCache.at < 30_000) return localModelCache.name;
  try {
    const response = await fetch(`${OLLAMA_URL}/api/tags`, { signal: AbortSignal.timeout(4_000) });
    const payload = response.ok ? ((await response.json()) as { models?: { name: string }[] }) : null;
    const name = payload?.models?.[0]?.name ?? null;
    localModelCache = { at: Date.now(), name };
    return name;
  } catch {
    localModelCache = { at: Date.now(), name: null };
    return null;
  }
}

const ollama: Provider = {
  id: "ollama",
  ready: () => true, // decided by whether a model is actually pulled
  models: () => {
    const name = process.env.OLLAMA_MODEL || "";
    return { light: name, heavy: name };
  },
  async run(ask, model) {
    const name = model || (await firstLocalModel());
    if (!name) throw new Error("no local model pulled");

    const response = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: name,
        stream: false,
        options: { temperature: ask.temperature ?? 0.8, num_predict: ask.maxTokens ?? 1800 },
        messages: [
          { role: "system", content: ask.system },
          { role: "user", content: ask.user },
        ],
      }),
      // a model on a laptop is slower than a datacentre
      signal: AbortSignal.timeout(180_000),
    });

    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(payload?.error ?? `ollama ${response.status}`);
    const text = payload?.message?.content;
    if (!text || !text.trim()) throw new Error("ollama returned an empty answer");
    return text;
  },
};

function registry(): Record<string, Provider> {
  return {
    groq: openAiCompatible("groq", {
      url: "https://api.groq.com/openai/v1/chat/completions",
      key: process.env.GROQ_API_KEY,
      light: process.env.GROQ_LIGHT_MODEL || "openai/gpt-oss-20b",
      heavy: process.env.GROQ_MODEL || "openai/gpt-oss-120b",
    }),
    openrouter: openAiCompatible("openrouter", {
      url: "https://openrouter.ai/api/v1/chat/completions",
      key: process.env.OPENROUTER_API_KEY,
      // Both defaults cost nothing. Naming a paid model here is a deliberate act.
      light: process.env.OPENROUTER_LIGHT_MODEL || "openai/gpt-oss-20b:free",
      heavy: process.env.OPENROUTER_MODEL || "nvidia/nemotron-3-super-120b-a12b:free",
      headers: {
        "HTTP-Referer": process.env.PUBLIC_SITE_URL || "https://ai-flow.local",
        "X-Title": "AI FLOW",
      },
    }),
    together: openAiCompatible("together", {
      url: "https://api.together.xyz/v1/chat/completions",
      key: process.env.TOGETHER_API_KEY,
      light: process.env.TOGETHER_LIGHT_MODEL,
      heavy: process.env.TOGETHER_MODEL,
    }),
    anthropic,
    custom: openAiCompatible("custom", {
      url: process.env.CUSTOM_MODEL_URL || "",
      key: process.env.CUSTOM_MODEL_KEY,
      light: process.env.CUSTOM_LIGHT_MODEL,
      heavy: process.env.CUSTOM_MODEL,
    }),
    ollama,
  };
}

function order(): string[] {
  const configured = (process.env.MODEL_PROVIDERS || "groq,ollama")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
  const known = registry();
  return configured.filter((id) => id in known);
}

export async function ask(request: Ask): Promise<Answer> {
  const weight = request.weight ?? "light";
  const known = registry();
  const tried: string[] = [];
  const unsureFrom: string[] = [];

  // Providers listed here only get the easy questions. Anything involved skips
  // straight past them, so a small model never fumbles a comparison.
  const lightOnly = (process.env.MODEL_LIGHT_ONLY || "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);

  for (const id of order()) {
    const provider = known[id];
    if (!provider.ready()) {
      tried.push(`${id}: not configured`);
      continue;
    }
    if (weight === "heavy" && lightOnly.includes(id)) {
      tried.push(`${id}: skipped, heavy question`);
      continue;
    }
    const model = provider.models()[weight] || provider.models().heavy;
    try {
      const text = await provider.run(request, model);
      if (text.includes(UNSURE)) throw new Escalate(id);
      return { text, via: id, model: model || "auto", weight };
    } catch (error) {
      if (error instanceof Escalate) {
        tried.push(`${id}: unsure, escalated`);
        unsureFrom.push(id);
        continue;
      }
      tried.push(`${id}: ${error instanceof Error ? error.message.slice(0, 90) : "failed"}`);
    }
  }

  // Everyone answering "I do not know" is not a breakdown. It means the question
  // genuinely needs a person, and the caller should say so rather than show an
  // error to a customer who did nothing wrong.
  if (unsureFrom.length) {
    return {
      text: "",
      via: unsureFrom[unsureFrom.length - 1],
      model: "unsure",
      weight,
      unsure: true,
    };
  }

  throw new NoModelAvailable(tried);
}

/** What the workspace can show about which brains are reachable. */
export async function modelStatus() {
  const known = registry();
  const local = await firstLocalModel();
  return {
    order: order(),
    providers: order().map((id) => ({
      id,
      configured: id === "ollama" ? Boolean(local) : known[id].ready(),
      light: id === "ollama" ? local : known[id].models().light,
      heavy: id === "ollama" ? local : known[id].models().heavy,
    })),
  };
}
