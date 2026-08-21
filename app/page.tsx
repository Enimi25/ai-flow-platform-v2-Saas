import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarCheck,
  Check,
  GlobeHemisphereWest,
  InstagramLogo,
  Lightning,
  MetaLogo,
  ShieldCheck,
  WhatsappLogo,
} from "@phosphor-icons/react/dist/ssr";
import { CopyLine } from "@/components/copy-line";
import { DemoForm } from "@/components/demo-form";
import { SalesChat } from "@/components/sales-chat";
import Strand from "@/components/strand";
import { Orb } from "@/components/orb";
import Flow from "@/components/flow";
import s from "./landing.module.css";

const plans = [
  {
    name: "Website Agent",
    price: "$39",
    description: "For a business that needs a helpful AI agent on its website.",
    features: ["Website chat", "Lead capture", "Calendar booking"],
  },
  {
    name: "Connected Sales",
    price: "$99",
    description: "For teams handling leads across the website and social channels.",
    features: [
      "Everything in Website Agent",
      "Facebook Messenger replies",
      "Shared lead workspace",
      "Instagram and WhatsApp once verified",
    ],
    featured: true,
  },
  {
    name: "Growth Partner",
    price: "Custom",
    description: "For businesses that want AI FLOW working the funnel with them.",
    features: [
      "Everything in Connected Sales",
      "Follow up automation",
      "Funnel and script tuning",
      "A share of what the agent closes",
    ],
  },
];

/**
 * Capabilities of the system, not customer results. There are no customers to
 * quote yet, and inventing a "42% more leads" would be the fastest way to lose
 * the first one.
 */
const facts = [
  { figure: "4 sec", label: "to the first reply", note: "While the person is still on the page." },
  { figure: "24 / 7", label: "covered", note: "Nights, Sundays, the two weeks you are away." },
  { figure: "4", label: "channels, one inbox", note: "Site, Messenger, Instagram, WhatsApp." },
  { figure: "1 line", label: "to install", note: "Paste it once. Nothing else changes." },
];

const trades = [
  { trade: "Salon", asked: "Do you have anything Saturday morning?" },
  { trade: "Dental clinic", asked: "How much is a cleaning?" },
  { trade: "Car workshop", asked: "My brakes squeal, can you look today?" },
  { trade: "Fitness studio", asked: "Can I freeze my membership?" },
  { trade: "Repair service", asked: "Do you come out to my district?" },
  { trade: "Tutoring", asked: "Do you teach adults in the evening?" },
];

const limits = [
  {
    title: "It will not invent a price.",
    body: "If the number is not in what you gave it, it says so and asks how to reach you. A made-up price costs you the customer twice.",
  },
  {
    title: "It will not promise a time you have not opened.",
    body: "Appointments come from your real calendar. If the slot is not free, it is not offered.",
  },
  {
    title: "It hands over when it is out of its depth.",
    body: "A question it cannot answer becomes a lead with the question attached, in the language the customer wrote in.",
  },
  {
    title: "It never asks for a password or a card number.",
    body: "Not once, in any wording. The widget says so on screen, under every conversation.",
  },
];

const questions = [
  {
    q: "What languages does it speak?",
    a: "It replies in whatever language the person writes in, including Russian typed in Latin letters. You write your business description once, in one language; the agent translates as it goes.",
  },
  {
    q: "What happens when it does not know?",
    a: "It says it does not know rather than guessing, asks how to reach the person, and files the question so you can answer it yourself. You see it in the activity log the same minute.",
  },
  {
    q: "How long does setup take?",
    a: "Sign in, describe the business in a few lines, paste one line of code into your site. Most of the time goes into the description, not the code.",
  },
  {
    q: "Where do the contact details go?",
    a: "Into your workspace, and nowhere else. Nobody without your sign-in can read them, and you can export or delete the lot at any time.",
  },
  {
    q: "What if I want to stop?",
    a: "Remove the one line from your site and cancel. No notice period, no call to keep you.",
  },
];

export default function Home() {
  return (
    <main>
      <header className={s.mast}>
        <div className={s.mastIn}>
          <Link href="#top" className={s.brandLink} aria-label="AI FLOW home">
            <span className={s.mark}>AI</span>
            <span>AI FLOW</span>
          </Link>
          <nav className={s.mastNav} aria-label="Primary navigation">
            <Link href="#platform">Platform</Link>
            <Link href="#how-it-works">How it works</Link>
            <Link href="#pricing">Pricing</Link>
          </nav>
          <div className={s.mastRight}>
            <Link href="/login" className={s.signin}>Sign in</Link>
            <Link href="#demo" className="btn btn-sm">Request demo</Link>
          </div>
        </div>
      </header>

      <section className={s.hero} id="top">
        <Orb className={s.orb} />

        <div className={s.heroInner}>
          <p className={s.badge}>
            <i className={s.dot} /> AI sales agents for small business
          </p>

          <h1 className={s.title}>Turn every message into a customer.</h1>

          <p className={s.sub}>
            AI FLOW answers in seconds, learns what the person needs, keeps their
            contact details and books the appointment. On your site, Messenger,
            Instagram and WhatsApp.
          </p>

          <div className={s.heroActions}>
            <Link href="#demo" className="btn">
              Get started <ArrowRight weight="bold" />
            </Link>
            <Link href="#how-it-works" className={s.quiet}>
              See how it works <ArrowUpRight weight="bold" />
            </Link>
          </div>
        </div>
      </section>

      <section className={s.rail} aria-label="Supported channels">
        <div className={s.railIn}>
          <span><GlobeHemisphereWest weight="regular" /> Website</span>
          <span><MetaLogo weight="regular" /> Facebook</span>
          <span><InstagramLogo weight="regular" /> Instagram</span>
          <span><WhatsappLogo weight="regular" /> WhatsApp</span>
          <span><CalendarCheck weight="regular" /> Google Calendar</span>
        </div>
      </section>

      <section className={s.facts} aria-label="What changes">
        <div className={s.factGrid}>
          {facts.map((fact) => (
            <div key={fact.label} className={s.fact}>
              <p className={`num ${s.figure}`}>{fact.figure}</p>
              <p className={s.factLabel}>{fact.label}</p>
              <p className={s.factNote}>{fact.note}</p>
            </div>
          ))}
        </div>
      </section>

      <Flow />

      <section className={s.bento} id="platform">
        <div className={s.bentoHead}>
          <h2 className="h2">One agent. A complete path to sale.</h2>
          <p className="body">
            AI FLOW connects a useful customer reply to the business action that should follow.
          </p>
        </div>

        <div className={s.bentoGrid}>
          <article className={`panel ${s.cell} ${s.cellWide}`}>
            <Lightning size={34} weight="fill" />
            <h3>Reply while intent is high.</h3>
            <p>Answer the question, understand what the customer needs, and move toward one useful action.</p>
            <div className={s.talk}>
              <p>Do you install on weekends?</p>
              <p className={s.agent}>Yes. Saturday slots are open. Want me to check a time for you?</p>
              <p>Saturday morning if possible.</p>
              <p className={s.agent}>Booked for 10:00. I have sent the details to your email.</p>
            </div>
          </article>

          <article className={`panel ${s.cell} ${s.cellTint}`}>
            <CalendarCheck size={34} weight="fill" />
            <h3>Book qualified calls</h3>
            <p>Collect contact details and offer the right appointment while the customer is still reading.</p>
            <Link href="/calendar" className={s.cellLink}>Open calendar <ArrowUpRight weight="bold" /></Link>
          </article>

          <article className={`panel ${s.cell} ${s.cellTexture}`}>
            <div className={s.texture}>
              <Strand rungs={22} radius={72} gap={20} step={22} spin={220} />
            </div>
            <ShieldCheck size={34} weight="fill" />
            <h3>Every channel in one place</h3>
            <p>Connection health and permissions live in a single protected workspace.</p>
            <Link href="/social-accounts" className={s.cellLink}>Open channels <ArrowUpRight weight="bold" /></Link>
          </article>
        </div>
      </section>

      <section className={s.trades} aria-label="Who this is for">
        <div className={s.tradesHead}>
          <h2 className="h2">The question your business gets every day.</h2>
          <p className="body">
            The agent learns yours from a description you write once. These are the ones it already handles.
          </p>
        </div>
        <ul className={s.tradeGrid}>
          {trades.map((item) => (
            <li key={item.trade} className={s.trade}>
              <span className={s.tradeName}>{item.trade}</span>
              <p>&ldquo;{item.asked}&rdquo;</p>
            </li>
          ))}
        </ul>
      </section>

      <section className={s.install} id="install">
        <div className={`panel ${s.installPanel}`}>
          <div>
            <h2 className="h2">One line, and it is live.</h2>
            <p className="body">
              Paste it before the closing body tag of your site. No plugin, no rebuild, nothing
              else on the page changes. Sign in and the line comes back with your own id in it.
            </p>
            <Link href="/install" className={s.cellLink}>
              Read the setup guide <ArrowUpRight weight="bold" />
            </Link>
          </div>
          <CopyLine text={'<script src="https://aiflow.forum/widget.js" data-company-id="your-id"></script>'} />
        </div>
      </section>

      <section className={s.plans} id="pricing">
        <div className={s.plansHead}>
          <h2 className="h2">Start with the channel that matters.</h2>
          <p className="body">Clear monthly plans. Add deeper integrations as the sales process grows.</p>
        </div>

        <div className={s.planGrid}>
          {plans.map((plan) => (
            <article key={plan.name} className={`panel ${s.plan} ${plan.featured ? s.featured : ""}`}>
              <div>
                <h3>{plan.name}</h3>
                <p>{plan.description}</p>
              </div>
              <p className={`price num ${s.price}`}>
                {plan.price}<span>/month</span>
              </p>
              <ul>
                {plan.features.map((feature) => (
                  <li key={feature}><Check weight="bold" size={17} />{feature}</li>
                ))}
              </ul>
              <Link href="#demo" className={plan.featured ? "btn" : "btn btn-ghost"}>Request demo</Link>
            </article>
          ))}
        </div>
      </section>

      <section className={s.limits} aria-label="What the agent will not do">
        <div className={s.limitsHead}>
          <h2 className="h2">What it will not do.</h2>
          <p className="body">
            An agent that guesses costs more than one that admits it does not know. These are hard
            rules, not settings you have to remember to switch on.
          </p>
        </div>
        <div className={s.limitGrid}>
          {limits.map((limit) => (
            <article key={limit.title} className={`panel ${s.limit}`}>
              <ShieldCheck size={26} weight="fill" />
              <h3>{limit.title}</h3>
              <p>{limit.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={s.faq} aria-label="Questions">
        <h2 className="h2">Questions people ask first.</h2>
        <div className={s.faqList}>
          {questions.map((item) => (
            <details key={item.q} className={s.q}>
              <summary>{item.q}</summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className={s.cta} id="demo">
        <div className={`panel ${s.ctaPanel}`}>
          <div className={s.ctaCopy}>
            <h2 className="h2">Give us one real customer question.</h2>
            <p className="body">
              We will show how AI FLOW answers it, captures the intent, and creates the next action.
            </p>
          </div>
          <div className={s.ctaForm}>
            <DemoForm />
          </div>
        </div>
      </section>

      <footer className={s.foot}>
        <div className={s.footIn}>
          <Link href="#top" className={s.brandLink}>
            <span className={s.mark}>AI</span>
            <span>AI FLOW</span>
          </Link>
          <a href="mailto:baskinltd@yahoo.com">baskinltd@yahoo.com</a>
          <div className={s.footLinks}>
            <Link href="/about">About</Link>
            <a href="https://www.facebook.com/61589383208797/" target="_blank" rel="noreferrer">Facebook</a>
            <Link href="/privacy">Privacy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/refunds">Refunds</Link>
          </div>
        </div>
      </footer>

      <SalesChat />
    </main>
  );
}
