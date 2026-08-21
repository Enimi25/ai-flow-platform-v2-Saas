"use client";

import { SignOut } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import styles from "./app-shell.module.css";

export function LogoutButton({ authenticated }: { authenticated: boolean }) {
  const router = useRouter();
  if (!authenticated) return null;
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }
  return <button className={styles.logout} onClick={logout} aria-label="Sign out" title="Sign out"><SignOut /></button>;
}
