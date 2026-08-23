"use client";

import { FormEvent, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react";

type FormState = "idle" | "loading" | "success" | "error";

export function DemoForm() {
  const [state, setState] = useState<FormState>("idle");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/demo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.fromEntries(form)) });
      const data = (await response.json()) as { message?: string };
      if (!response.ok) { setState("error"); setMessage(data.message || "Please check the form and try again."); return; }
      setState("success"); setMessage(data.message || "Request received. We will contact you shortly."); event.currentTarget.reset();
    } catch {
      setState("error");
      setMessage("We could not send your request. Please try again in a moment.");
    }
  }

  return (
    <form className="demo-form" onSubmit={submit} noValidate>
      <label htmlFor="name">Name</label><input id="name" name="name" autoComplete="name" required minLength={2} />
      <label htmlFor="email">Business email</label><input id="email" name="email" type="email" autoComplete="email" required />
      <label htmlFor="question">What does your business do?</label><textarea id="question" name="question" rows={4} required minLength={3} placeholder="A hair salon on Oxford Street. Cut 45, colour from 110. Tuesday to Sunday, 10 to 20." /><small className="demo-hint">A short answer is enough. This is what the agent learns from.</small>
      <input className="honeypot" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
      <button className="button" type="submit" disabled={state === "loading"}>{state === "loading" ? "Sending..." : <>Request demo <ArrowRight weight="bold" /></>}</button>
      <p className={`form-message ${state}`} aria-live="polite">{message}</p>
    </form>
  );
}
