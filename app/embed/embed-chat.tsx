"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, SpeakerHigh, SpeakerSlash } from "@phosphor-icons/react";
import { Dalmatian, type Mood } from "@/components/dalmatian";
import s from "./embed.module.css";

type Message = { role: "agent" | "customer"; text: string };

/** Kept in the browser so a returning visitor continues the same thread. */
function visitorId(companyId: string) {
  const key = `ai_flow_visitor_${companyId}`;
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export function EmbedChat({
  companyId,
  assistantName,
  welcome,
}: {
  companyId: string;
  assistantName: string;
  welcome: string;
}) {
  const store = `ai_flow_embed_${companyId}`;
  const [messages, setMessages] = useState<Message[]>([]);
  const [typing, setTyping] = useState("");
  const [loading, setLoading] = useState(false);
  const [voice, setVoice] = useState(true);
  const [ready, setReady] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const timer = useRef<number | null>(null);

  const mood: Mood = loading ? "thinking" : typing ? "speaking" : "listening";

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(store) || "[]") as Message[];
      setMessages(saved.length ? saved.slice(-30) : [{ role: "agent", text: welcome }]);
      setVoice(localStorage.getItem(`${store}_voice`) !== "off");
    } catch {
      setMessages([{ role: "agent", text: welcome }]);
    }
    setReady(true);
  }, [store, welcome]);

  useEffect(() => {
    if (ready) localStorage.setItem(store, JSON.stringify(messages.slice(-30)));
  }, [messages, ready, store]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current);
    window.speechSynthesis?.cancel();
  }, []);

  const reveal = useCallback(
    (text: string) => {
      if (voice && window.speechSynthesis) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.04;
        utterance.pitch = 1.12;
        window.speechSynthesis.speak(utterance);
      }
      let index = 0;
      const step = () => {
        index += 1;
        setTyping(text.slice(0, index));
        if (index < text.length) timer.current = window.setTimeout(step, 16);
        else {
          timer.current = null;
          setTyping("");
          setMessages((current) => [...current, { role: "agent", text }]);
        }
      };
      step();
    },
    [voice],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = String(new FormData(form).get("message") || "").trim().slice(0, 600);
    if (!message || loading) return;

    setMessages((current) => [...current, { role: "customer", text: message }]);
    form.reset();
    setLoading(true);
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, companyId, visitorId: visitorId(companyId) }),
      });
      const data = (await response.json()) as { reply?: string; message?: string };
      reveal(response.ok && data.reply ? data.reply : data.message || "I cannot reach my brain right now. Leave your email and a person will come back to you.");
    } catch {
      reveal("I cannot reach my brain right now. Leave your email and a person will come back to you.");
    } finally {
      setLoading(false);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function toggleVoice() {
    setVoice((current) => {
      const next = !current;
      localStorage.setItem(`${store}_voice`, next ? "on" : "off");
      if (!next) window.speechSynthesis?.cancel();
      return next;
    });
  }

  return (
    <div className={s.shell}>
      <header className={s.head}>
        <span className={s.avatar}><Dalmatian mood={mood} size={36} /></span>
        <div className={s.who}>
          <b>{assistantName}</b>
          <small>Usually replies in seconds</small>
        </div>
        <button type="button" onClick={toggleVoice} aria-label={voice ? "Turn the voice off" : "Turn the voice on"}>
          {voice ? <SpeakerHigh weight="fill" /> : <SpeakerSlash weight="fill" />}
        </button>
      </header>

      <div className={s.log} ref={scroller} aria-live="polite">
        {messages.map((message, index) => (
          <p key={`${message.role}-${index}`} data-role={message.role}>{message.text}</p>
        ))}
        {typing && <p data-role="agent">{typing}<i className={s.caret} /></p>}
        {loading && !typing && <p data-role="agent" className={s.dots}><span /><span /><span /></p>}
      </div>

      <form className={s.form} onSubmit={submit}>
        <label htmlFor="embed-message" className="sr-only">Your message</label>
        <input ref={inputRef} id="embed-message" name="message" placeholder="Type your question…" autoComplete="off" maxLength={600} />
        <button type="submit" disabled={loading} aria-label="Send"><ArrowUp weight="bold" /></button>
      </form>

      <small className={s.footer}>Do not share passwords or card details.</small>
    </div>
  );
}
