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
    const response = await fetch("/api/demo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.fromEntries(form)) });
    const data = (await response.json()) as { message?: string };
    if (!response.ok) { setState("error"); setMessage(data.message || "Please try again."); return; }
    setState("success"); setMessage("Request received. We will contact you shortly."); event.currentTarget.reset();
  }

  return (
    <form className="demo-form" onSubmit={submit} noValidate>
      <label htmlFor="name">Name</label><input id="name" name="name" autoComplete="name" required minLength={2} />
      <label htmlFor="email">Business email</label><input id="email" name="email" type="email" autoComplete="email" required />
      <label htmlFor="question">A customer question you receive</label><textarea id="question" name="question" rows={3} required minLength={8} />
      <input className="honeypot" name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" />
      <button className="button" type="submit" disabled={state === "loading"}>{state === "loading" ? "Sending..." : <>Request demo <ArrowRight weight="bold" /></>}</button>
      <p className={`form-message ${state}`} aria-live="polite">{message}</p>
    </form>
  );
}
