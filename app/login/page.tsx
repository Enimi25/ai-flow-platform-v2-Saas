import type { Metadata } from "next";
import Link from "next/link";
import { LoginForm } from "./login-form";
import styles from "./login.module.css";

export const metadata: Metadata = { title: "Sign in | AI FLOW" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ returnTo?: string; reason?: string }> }) {
  const params = await searchParams;
  const returnTo = params.returnTo?.startsWith("/") && !params.returnTo.startsWith("//") ? params.returnTo : "/social-accounts";
  return <main className={styles.page}><section className={styles.panel}><Link href="/" className={styles.brand}><span>AI</span> AI FLOW</Link><div className={styles.copy}><h1>Welcome back</h1><p>{params.reason === "session" ? "Your previous session ended. Sign in to continue where you left off." : "Sign in to manage your AI agents and connected channels."}</p></div><div className={styles.google}><a className="btn" href="/api/auth/google?next=/calendar/confirm">Continue with Google</a><small>One tap. Signs you in and connects the booking calendar in the same step.</small></div><div className={styles.or}><span>or use a password</span></div><LoginForm returnTo={returnTo} /><p className={styles.security}>Your password is sent only to the server. The browser receives a secure session cookie, not an access token.</p></section><aside className={styles.aside}><div><h2>Keep every channel in one workspace.</h2><ul><li>See connection health at a glance</li><li>Recover expired permissions</li><li>Control which accounts AI FLOW can use</li></ul></div></aside></main>;
}
