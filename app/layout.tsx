import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./design.css";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://aiflow.forum"),
  title: "AI FLOW | AI sales agents for small business",
  description: "Reply to customers, capture qualified leads, and book appointments from every conversation.",
  openGraph: {
    title: "AI FLOW | Turn messages into customers",
    description: "AI sales agents for websites and customer messaging.",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geist.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
