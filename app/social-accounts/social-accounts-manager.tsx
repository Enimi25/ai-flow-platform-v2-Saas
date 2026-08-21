"use client";

import { useState } from "react";
import { ArrowSquareOut, Check, FacebookLogo, InstagramLogo, LockKey, Warning, WhatsappLogo } from "@phosphor-icons/react";
import styles from "./social.module.css";

type Provider = "facebook" | "instagram" | "whatsapp";
const channels = [
  { id: "facebook" as Provider, name: "Facebook Messenger", icon: FacebookLogo, description: "Reply to messages from your connected Facebook Page.", requirement: "You need admin access to the Facebook Page.", permissions: ["Read Page conversations", "Send replies", "Capture lead details"] },
  { id: "instagram" as Provider, name: "Instagram", icon: InstagramLogo, description: "Handle direct messages from a professional Instagram account.", requirement: "Instagram must be professional and linked to a Facebook Page.", permissions: ["Read direct messages", "Send replies", "Identify conversation source"] },
  { id: "whatsapp" as Provider, name: "WhatsApp Business", icon: WhatsappLogo, description: "Use an approved WhatsApp Business number for customer conversations.", requirement: "A verified Meta Business portfolio and eligible phone number are required.", permissions: ["Receive customer messages", "Send approved replies", "Track conversation status"] },
];

export function SocialAccountsManager({ authenticated, setupProvider }: { authenticated: boolean; setupProvider?: string }) {
  const [selected, setSelected] = useState<Provider>(channels[0].id);
  const channel = channels.find((item) => item.id === selected)!;
  const Icon = channel.icon;
  return <div className={styles.manager}><section className={styles.summary} aria-label="Connection summary"><div><strong>0</strong><span>Connected</span></div><div><strong>3</strong><span>Available channels</span></div><div><strong>0</strong><span>Need attention</span></div></section>{setupProvider && <div className={styles.setupNotice}><Warning weight="fill" /><div><b>Connection setup is not complete</b><p>Add the OAuth URL and Meta credentials for {setupProvider}, then try again.</p></div></div>}<div className={styles.board}><section className={styles.channelList}><div className={styles.listHeader}><h2>Available channels</h2><p>Select a channel to review requirements and permissions.</p></div>{channels.map(({ id, name, icon: ChannelIcon, description }) => <button key={id} onClick={() => setSelected(id)} className={selected === id ? styles.selected : undefined}><span className={styles.channelIcon}><ChannelIcon weight="fill" /></span><span><b>{name}</b><small>{description}</small></span><em>Not connected</em></button>)}</section><aside className={styles.details}><div className={styles.detailTitle}><span className={styles.channelIcon}><Icon weight="fill" /></span><div><h2>{channel.name}</h2><p>Not connected</p></div></div><p className={styles.requirement}>{channel.requirement}</p><div className={styles.permissionBlock}><h3>AI FLOW will request</h3><ul>{channel.permissions.map((permission) => <li key={permission}><Check weight="bold" />{permission}</li>)}</ul></div><div className={styles.privacy}><LockKey /><p>Provider tokens stay on the server and are never exposed in the browser.</p></div>{authenticated ? <a className={styles.connectButton} href={`/api/social/connect/${channel.id}`}>Connect {channel.name}<ArrowSquareOut weight="bold" /></a> : <a className={styles.connectButton} href="/login?returnTo=/social-accounts&reason=session">Sign in to connect</a>}<p className={styles.actionHelp}>You can review requested permissions before approving access at Meta.</p></aside></div></div>;
}
