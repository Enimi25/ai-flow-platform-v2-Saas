"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, SpeakerHigh, SpeakerSlash, X } from "@phosphor-icons/react";
import { Dalmatian, type Mood } from "./dalmatian";
import s from "./sales-chat.module.css";

type Message = { role: "agent" | "customer"; text: string };

const STORE = "ai_flow_chat_v1";
const OPENER = "Hey. I am Flo. Ask me about pricing, setup, or what happens to a message at 2am.";

type Remembered = { name?: string; messages: Message[] };

function load(): Remembered {
  try {
    const raw = localStorage.getItem(STORE);
    if (!raw) return { messages: [] };
    const parsed = JSON.parse(raw) as Remembered;
    return { name: parsed.name, messages: Array.isArray(parsed.messages) ? parsed.messages.slice(-30) : [] };
  } catch {
    return { messages: [] };
  }
}

/** Picks up a first name when the visitor offers one, so a return visit knows them. */
function nameFrom(text: string) {
  const match = text.match(/\b(?:my name is|i am|i'm|меня зовут|я)\s+([A-Za-zА-Яа-яЁё][\w'-]{1,20})/i);
  const found = match?.[1];
  if (!found) return undefined;
  return found[0].toUpperCase() + found.slice(1);
}

/** Kept in the browser so a returning visitor continues the same thread. */
function visitorId() {
  const key = "ai_flow_visitor";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export function SalesChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [name, setName] = useState<string | undefined>();
  const [typing, setTyping] = useState("");
  const [loading, setLoading] = useState(false);
  const [voice, setVoice] = useState(true);
  const [teaser, setTeaser] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const revealTimer = useRef<number | null>(null);

  const mood: Mood = loading ? "thinking" : typing ? "speaking" : open ? "listening" : "idle";

  // restore the previous visit
  useEffect(() => {
    const saved = load();
    setName(saved.name);
    setMessages(saved.messages.length ? saved.messages : [{ role: "agent", text: OPENER }]);
    setVoice(localStorage.getItem(`${STORE}_voice`) !== "off");
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    localStorage.setItem(STORE, JSON.stringify({ name, messages: messages.slice(-30) }));
  }, [messages, name, ready]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  // a nudge from the corner, once, only if the chat is still shut
  useEffect(() => {
    if (!ready || open) return;
    const seen = sessionStorage.getItem(`${STORE}_teaser`);
    if (seen) return;
    const timer = window.setTimeout(() => {
      setTeaser(name ? `Good to see you again, ${name}.` : "Got a customer question? Try me.");
      sessionStorage.setItem(`${STORE}_teaser`, "1");
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [ready, open, name]);

  const speak = useCallback(
    (text: string) => {
      if (!voice || typeof window === "undefined" || !window.speechSynthesis) return;
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.04;
      utterance.pitch = 1.12;
      window.speechSynthesis.speak(utterance);
    },
    [voice],
  );

  /** Reveals the reply the way a person types it, then commits it to the log. */
  const reveal = useCallback(
    (text: string) => {
      speak(text);
      let index = 0;
      const step = () => {
        index += 1;
        setTyping(text.slice(0, index));
        if (index < text.length) {
          revealTimer.current = window.setTimeout(step, 16);
        } else {
          revealTimer.current = null;
          setTyping("");
          setMessages((current) => [...current, { role: "agent", text }]);
        }
      };
      step();
    },
    [speak],
  );

  useEffect(() => () => {
    if (revealTimer.current) window.clearTimeout(revealTimer.current);
    window.speechSynthesis?.cancel();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = String(new FormData(form).get("message") || "").trim().slice(0, 600);
    if (!message || loading) return;

    const spotted = nameFrom(message);
    if (spotted && !name) setName(spotted);

    setMessages((current) => [...current, { role: "customer", text: message }]);
    form.reset();
    setLoading(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, visitorId: visitorId() }),
      });
      const data = (await response.json()) as { reply?: string; message?: string };
      reveal(
        response.ok && data.reply
          ? data.reply
          : data.message || "I cannot reach my brain right now. Book a demo and a person will pick this up.",
      );
    } catch {
      reveal("I cannot reach my brain right now. Book a demo and a person will pick this up.");
    } finally {
      setLoading(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function toggleVoice() {
    setVoice((current) => {
      const next = !current;
      localStorage.setItem(`${STORE}_voice`, next ? "on" : "off");
      if (!next) window.speechSynthesis?.cancel();
      return next;
    });
  }

  function launch() {
    setTeaser(null);
    setOpen((value) => {
      if (value) window.speechSynthesis?.cancel();
      return !value;
    });
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  return (
    <div className={s.root}>
      {open && (
        <section className={s.panel} aria-label="AI FLOW assistant">
          <header className={s.head}>
            <span className={s.headAvatar}><Dalmatian mood={mood} size={44} /></span>
            <div className={s.who}>
              <b>Flo</b>
              <small>{name ? `talking with ${name}` : "AI FLOW assistant"}</small>
            </div>
            <button type="button" onClick={toggleVoice} aria-label={voice ? "Turn the voice off" : "Turn the voice on"}>
              {voice ? <SpeakerHigh weight="fill" /> : <SpeakerSlash weight="fill" />}
            </button>
            <button type="button" onClick={launch} aria-label="Close chat"><X weight="bold" /></button>
          </header>

          <div className={s.log} ref={scroller} aria-live="polite">
            {messages.map((message, index) => (
              <p key={`${message.role}-${index}`} data-role={message.role}>{message.text}</p>
            ))}
            {typing && <p data-role="agent">{typing}<i className={s.caret} /></p>}
            {loading && !typing && (
              <p data-role="agent" className={s.dots}><span /><span /><span /></p>
            )}
          </div>

          <form className={s.form} onSubmit={submit}>
            <label htmlFor="flo-message" className="sr-only">Your message</label>
            <input
              ref={inputRef}
              id="flo-message"
              name="message"
              placeholder="Ask Flo anything…"
              autoComplete="off"
              maxLength={600}
            />
            <button type="submit" disabled={loading} aria-label="Send message"><ArrowUp weight="bold" /></button>
          </form>

          <small className={s.disclaimer}>Do not share passwords or card details.</small>
        </section>
      )}

      {teaser && !open && (
        <button type="button" className={s.teaser} onClick={launch}>
          {teaser}
        </button>
      )}

      <button className={s.launcher} type="button" aria-expanded={open} onClick={launch}>
        <Dalmatian mood={open ? "listening" : "idle"} size={40} />
        <span>{open ? "Close" : "Ask Flo"}</span>
      </button>
    </div>
  );
}
