import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ChatCircleDots, EnvelopeSimple, FacebookLogo, GlobeHemisphereWest } from "@phosphor-icons/react/dist/ssr";

export const metadata: Metadata = { title: "About AI FLOW | AI sales automation" };

export default function AboutPage() {
  return <main className="about-page">
    <header className="site-header"><Link href="/" className="brand"><span className="brand-mark">AI</span><span>AI FLOW</span></Link><div className="header-actions"><Link href="/login" className="login-link">Sign in</Link><Link href="/#demo" className="button button-small">Request demo</Link></div></header>
    <section className="about-hero">
      <div><p className="about-label"><GlobeHemisphereWest weight="fill" /> Remote-first AI software</p><h1>Built for the conversations that grow a business.</h1><p>AI FLOW gives small teams one practical place to manage customer messages, qualified leads, appointments, and connected sales channels.</p><Link href="/#demo" className="button">Talk to our team <ArrowRight weight="bold" /></Link></div>
      <aside className="hq-card"><span className="hq-icon"><GlobeHemisphereWest weight="fill" /></span><p>How we work</p><h2>Online, across customer channels</h2><small>Product demonstrations and onboarding sessions are available remotely by appointment.</small></aside>
    </section>
    <section className="about-content">
      <article><h2>What we do</h2><p>We connect an intelligent first reply with the business action that follows: a qualified lead, a booking, a payment path, or a useful follow-up.</p></article>
      <article><h2>How to reach us</h2><p>Tell us how you receive customer messages today. We will show you the right first AI FLOW setup for your business.</p><div className="contact-options"><Link href="/#demo"><ChatCircleDots /> Request a demo <ArrowRight /></Link><a href="mailto:baskinltd@yahoo.com"><EnvelopeSimple /> baskinltd@yahoo.com <ArrowRight /></a><a href="https://www.facebook.com/61589383208797/" target="_blank" rel="noreferrer"><FacebookLogo /> AI FLOW on Facebook <ArrowRight /></a></div></article>
    </section>
    <footer><Link href="/" className="brand"><span className="brand-mark">AI</span><span>AI FLOW</span></Link><p>Remote demos and onboarding by appointment</p><div><Link href="/privacy">Privacy</Link><Link href="/terms">Terms</Link><Link href="/refunds">Refunds</Link></div></footer>
  </main>;
}
