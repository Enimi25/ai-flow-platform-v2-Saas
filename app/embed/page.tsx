import type { Metadata } from "next";
import { getSettings } from "@/lib/settings/store";
import { EmbedChat } from "./embed-chat";
import "./embed.css";

export const metadata: Metadata = {
  title: "Chat",
  robots: { index: false, follow: false },
};

export default async function EmbedPage({
  searchParams,
}: {
  searchParams: Promise<{ company?: string }>;
}) {
  const { company } = await searchParams;
  const companyId = company?.slice(0, 80) || "preview";
  const settings = await getSettings(companyId);

  return (
    <EmbedChat
      companyId={companyId}
      assistantName={settings.assistantName || "Flo"}
      welcome={settings.welcome || "Hi. What can I help you with today?"}
    />
  );
}
