"use client";

import { FormEvent, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import styles from "./login.module.css";

export function LoginForm({ returnTo }: { returnTo: string }) {
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setState("loading"); setMessage("");
    try {
      const form = new FormData(event.currentTarget);
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      const result = await response.json().catch(() => ({})) as { message?: string };
      if (!response.ok) { setState("error"); setMessage(result.message || "Sign in failed. Try again."); return; }
      window.location.assign(returnTo);
    } catch {
      setState("error");
      setMessage("The account service could not be reached. Check your connection and try again.");
    }
  }
  return <form className={styles.form} onSubmit={submit}><label htmlFor="email">Email</label><input id="email" name="email" type="email" autoComplete="email" required /><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" minLength={8} required /><button type="submit" disabled={state === "loading"}>{state === "loading" ? "Signing in..." : <>Sign in <ArrowRight weight="bold" /></>}</button><p className={styles.error} aria-live="polite">{message}</p></form>;
}
