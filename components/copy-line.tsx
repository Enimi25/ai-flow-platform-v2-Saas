"use client";

import { useState } from "react";
import { Check, Copy } from "@phosphor-icons/react";
import s from "./copy-line.module.css";

/**
 * The install snippet, with a button that actually copies it.
 *
 * Showing code a visitor has to select by hand undercuts the claim that setup
 * is one line — so the line copies itself.
 */
export function CopyLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard is blocked in some embedded contexts; the code is on screen
      // either way, so there is nothing useful to say here
    }
  }

  return (
    <div className={s.line}>
      <code>{text}</code>
      <button type="button" onClick={copy} aria-label="Copy the install line">
        {copied ? <Check weight="bold" /> : <Copy weight="bold" />}
        <span>{copied ? "Copied" : "Copy"}</span>
      </button>
    </div>
  );
}
