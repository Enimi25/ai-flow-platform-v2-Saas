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
import { DemoForm } from "@/components/demo-form";
import { SalesChat } from "@/components/sales-chat";
import Strand from "@/components/strand";
import { Scene } from "@/components/scene";
import { Spiral } from "@/components/spiral";
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
            <Link href="#demo" className={s.pearl}>Request demo</Link>
          </div>
        </div>
      </header>

      <section className={s.hero} id="top">
        <Scene className={s.orb} />

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
            <Link href="#demo" className={s.pearlBig}>
              Get started <ArrowRight weight="bold" />
            </Link>
            <Link href="#how-it-works" className={s.quiet}>
              See how it works <ArrowUpRight weight="bold" />
            </Link>
          </div>
        </div>

        <nav className={s.rail2} aria-label="What are you looking for">
          <span>What are you looking for?</span>
          <Link href="#platform">&rarr; Website agent</Link>
          <Link href="#how-it-works">&rarr; Social channels</Link>
          <Link href="/install">&rarr; Install the widget</Link>
          <Link href="#pricing">&rarr; Pricing</Link>
          <Link href="#demo">&rarr; Ask me anything</Link>
        </nav>
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

      <Spiral />

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
