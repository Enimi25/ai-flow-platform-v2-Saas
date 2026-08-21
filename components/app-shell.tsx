import Link from "next/link";
import {
  Bell,
  CalendarBlank,
  ChartLineUp,
  ChatCircleDots,
  CreditCard,
  Code,
  GearSix,
  House,
  Pulse as PulseIcon,
  MegaphoneSimple,
  PlugsConnected,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";
import type { Session } from "@/lib/session";
import { LogoutButton } from "./logout-button";
import styles from "./app-shell.module.css";

type Section = "overview" | "conversations" | "leads" | "calendar" | "content" | "activity" | "install" | "analytics" | "billing" | "social" | "settings";

const items = [
  { id: "overview" as Section, label: "Overview", href: "/dashboard", icon: House },
  { id: "conversations" as Section, label: "Conversations", href: "/conversations", icon: ChatCircleDots },
  { id: "leads" as Section, label: "Leads", href: "/leads", icon: UsersThree },
  { id: "calendar" as Section, label: "Calendar", href: "/calendar", icon: CalendarBlank },
  { id: "content" as Section, label: "Content", href: "/content", icon: MegaphoneSimple },
  { id: "activity" as Section, label: "Activity", href: "/activity", icon: PulseIcon },
  { id: "install" as Section, label: "Install", href: "/install", icon: Code },
  { id: "social" as Section, label: "Social accounts", href: "/social-accounts", icon: PlugsConnected },
  { id: "analytics" as Section, label: "Analytics", href: "/analytics", icon: ChartLineUp },
  { id: "billing" as Section, label: "Billing", href: "/billing", icon: CreditCard },
  { id: "settings" as Section, label: "Settings", href: "/settings", icon: GearSix },
];

export function AppShell({ active, session, children }: { active: Section; session: Session | null; children: React.ReactNode }) {
  const workspaceName = session?.companyId || (session?.role === "platform_admin" ? "Platform administration" : "AI FLOW demo");
  return <main className={styles.app}><aside className={styles.sidebar}><Link href="/" className={styles.brand}><span>AI</span><b>AI FLOW</b></Link><nav aria-label="Workspace">{items.map(({ id, label, href, icon: Icon }) => <Link key={id} href={href} className={active === id ? styles.active : undefined} aria-current={active === id ? "page" : undefined}><Icon /> <span>{label}</span></Link>)}</nav><div className={styles.sidebarFoot}><div className={styles.avatar}>{session?.email.slice(0,1).toUpperCase() || "G"}</div><div className={styles.account}><b>{session?.email || "Guest session"}</b><span>{session?.role || "Sign in required"}</span></div><a className={styles.support} href="mailto:baskinltd@yahoo.com">Support: baskinltd@yahoo.com</a><LogoutButton authenticated={Boolean(session)} /></div></aside><section className={styles.workspace}><header className={styles.topbar}><div><span>Workspace</span><b>{workspaceName}</b></div><button aria-label="Notifications unavailable" title="Notifications are not connected yet" disabled><Bell /></button></header><div className={styles.content}>{children}</div></section></main>;
}
