"use client";

import { FormEvent, useState } from "react";
import { ArrowRight } from "@phosphor-icons/react";
import styles from "./login.module.css";

type Mode = "signin" | "signup";

export function LoginForm({ returnTo }: { returnTo: string }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");
    setMessage("");

    const form = new FormData(event.currentTarget);
    const route = mode === "signup" ? "/api/auth/register" : "/api/auth/login";

    try {
      const response = await fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      const result = (await response.json().catch(() => ({}))) as { message?: string };

      if (!response.ok) {
        setState("error");
        // an existing account is not an error worth a red line — just switch
        if (response.status === 409) {
          setMode("signin");
          setMessage("You already have an account. Enter your password to sign in.");
          return;
        }
        setMessage(result.message || "Something went wrong. Try again.");
        return;
      }
      window.location.assign(returnTo);
    } catch {
      setState("error");
      setMessage("Could not reach the server. Check your connection and try again.");
    }
  }

  const creating = mode === "signup";

  return (
    <>
      <form className={styles.form} onSubmit={submit}>
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" autoComplete="email" required />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete={creating ? "new-password" : "current-password"}
          minLength={8}
          required
        />

        <button type="submit" disabled={state === "loading"}>
          {state === "loading"
            ? creating
              ? "Creating your workspace..."
              : "Signing in..."
            : (
              <>
                {creating ? "Create workspace" : "Sign in"} <ArrowRight weight="bold" />
              </>
            )}
        </button>

        <p className={styles.error} aria-live="polite">{message}</p>
      </form>

      <p className={styles.swap}>
        {creating ? "Already have an account?" : "No account yet?"}{" "}
        <button
          type="button"
          onClick={() => {
            setMode(creating ? "signin" : "signup");
            setState("idle");
            setMessage("");
          }}
        >
          {creating ? "Sign in" : "Create one"}
        </button>
      </p>
    </>
  );
}
