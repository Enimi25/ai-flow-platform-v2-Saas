import Link from "next/link";
import styles from "./workspace-page.module.css";

export function SessionBanner({ returnTo }: { returnTo: string }) {
  return <section className={styles.banner}><div><h2>Sign in to use live workspace data</h2><p>This preview contains no customer messages or personal data.</p></div><Link href={`/login?returnTo=${encodeURIComponent(returnTo)}&reason=session`}>Sign in</Link></section>;
}
