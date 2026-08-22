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
  { figure: "4 sec", label: "to answer", note: "They are still on the page when the reply comes." },
  { figure: "24 / 7", label: "always on", note: "Nights, Sundays, and the two weeks you are away." },
  { figure: "4", label: "channels, one place", note: "Site, Messenger, Instagram, WhatsApp." },
  { figure: "1 line", label: "to set up", note: "Paste it once. Nothing else changes." },
];

const trades = [
  { trade: "Salon", asked: "Do you have anything Saturday morning?" },
  { trade: "Dental clinic", asked: "How much is a cleaning?" },
  { trade: "Car workshop", asked: "My brakes squeal, can you look today?" },
  { trade: "Fitness studio", asked: "Can I freeze my membership?" },
  { trade: "Repair service", asked: "Do you come out to my district?" },
  { trade: "Tutoring", asked: "Do you teach adults in the evening?" },
];

/** The whole job, listed. This is the section a buyer reads twice. */
const doing = [
  {
    title: "We answer your customers",
    body: "Website, Messenger, Instagram and WhatsApp. In seconds, at any hour, in the language they wrote in. It uses your prices, your address, your hours. If it does not know the answer, it says so and asks for their number. It never guesses.",
    items: ["Four channels, one inbox", "Under five seconds", "Any language, any hour"],
  },
  {
    title: "We keep every lead",
    body: "Name, phone, email, where they came from, and the whole chat. Saved before the person even closes the window. A number typed in the middle of a sentence still gets saved. Nobody has to remember to write it down.",
    items: ["Captured automatically", "Full conversation attached", "Only your workspace sees it"],
  },
  {
    title: "We book the appointment",
    body: "Not a form that says we will call you back. The agent offers times that are really free, from your own opening hours. It checks again before booking, then confirms the exact date. It works from a direct message too.",
    items: ["Your real hours", "Conflict checked", "Books from social as well"],
  },
  {
    title: "We run your social accounts",
    body: "Up to three posts a day, in your language, at good hours for your timezone. The queue fills itself up, so there is never a quiet week.",
    items: ["Written and published", "Never invents a figure", "You can read the queue"],
  },
  {
    title: "We tell you what is happening",
    body: "One place with your chats, your leads, your calendar, your posts, and a log of everything that happened. Open it in the morning and last night is already there.",
    items: ["Live activity log", "Leads by channel", "Nothing hidden"],
  },
  {
    title: "We set it up",
    body: "You tell us what you do, in your own words. We connect your channels, set up the agent, and send you one line for your website. No plugin. Nothing else changes.",
    items: ["One line to install", "We connect the accounts", "Cancel by deleting the line"],
  },
];

/**
 * Real output, not marketing copy about output. These came out of the generator
 * for a dental clinic that had written four lines about itself, which is the
 * whole claim in one exhibit.
 */
const factoryPosts = [
  {
    channel: "Facebook",
    when: "Saturday, 11:00",
    body: "Вы проснулись с резкой болью в зубе и не знаете, что делать? Мы принимаем срочные случаи с болью без записи утром. Приходите на Ленина 8, осмотр 1500 руб.",
  },
  {
    channel: "Instagram",
    when: "Saturday, 17:00",
    body: "После праздников зубы потеряли белизну, а пятна от кофе не уходят? Профессиональная чистка - 5500 руб. Записывайтесь, мы работаем в субботу до 14:00.",
  },
  {
    channel: "Facebook",
    when: "Sunday, 11:00",
    body: "Перед началом учебного года стоит показать ребёнка стоматологу. Осмотр 1500 руб, принимаем с понедельника по пятницу с 9:00.",
  },
];

const factoryRules = [
  {
    rule: "It writes from what you wrote",
    body: "Your description is the only source. Prices, hours and services come from there, so a post can never advertise something you do not do.",
  },
  {
    rule: "It invents nothing",
    body: "No made-up discounts, no invented statistics, no fake customer quotes. If there is no figure, the post carries none.",
  },
  {
    rule: "It writes in your language",
    body: "Whatever language your description is in. A Russian business gets Russian posts, not translated English ones.",
  },
  {
    rule: "It posts at sensible hours",
    body: "Late morning and late afternoon, in your timezone, spread across days rather than dumped in one afternoon.",
  },
  {
    rule: "It only posts where you are connected",
    body: "Nothing is queued for a channel you have not linked, so you never find failures waiting for you at midnight.",
  },
  {
    rule: "Up to three a day, or one a week",
    body: "You set the pace and it holds it. The queue tops itself up before it runs dry, so there is never a week where nothing went out.",
  },
  {
    rule: "You stay in charge",
    body: "Everything sits in a queue you can read, edit or delete before it goes out. Turn the whole thing off in one switch.",
  },
];

const questions = [
  {
    q: "What if it tells my customer something wrong?",
    a: "It answers only from the description you wrote. If a price, a time or a service is not in there, it says it does not know and asks how to reach you, rather than inventing something. You can read every conversation it has had, word for word, and correct the description in a minute. Most wrong answers are a missing line in the description, not a broken agent.",
  },
  {
    q: "Where do my customers' details go, and who can see them?",
    a: "Into your workspace on our server, and nowhere else. Nobody without your sign-in can read a single contact, including other businesses using AI FLOW. We do not sell data, we do not use it for advertising, and we do not build a shared database out of it. You can export or delete everything at any time, and we erase it within 30 days of being asked.",
  },
  {
    q: "Which AI is behind this, and does my data train it?",
    a: "The reply is generated by a large language model — currently Groq and OpenRouter as a fallback. The text of a message is sent to them to compose the answer, which is how any AI assistant works. They process it, they do not own it, and it is not used to train public models. We say this plainly because you will be asked it by your own customers one day.",
  },
  {
    q: "How is this different from putting ChatGPT on my site?",
    a: "ChatGPT will happily invent your prices and promise a Tuesday you are closed. This agent knows your opening hours and offers only times that are genuinely free, checks the slot again before booking, files the contact, and hands over when it is out of its depth. The conversation is not the product. What happens after it is.",
  },
  {
    q: "What if I already have a CRM or a booking system?",
    a: "Then use AI FLOW for the part it does well — answering and qualifying — and export the leads. Everything it captures is yours to download. Direct integrations with common booking systems are the next thing we build, and the first customer who needs one gets it built for them.",
  },
  {
    q: "Do I need to know anything technical?",
    a: "No. You write four lines about your business in your own words. We connect the accounts and send you one line to paste, or paste it for you if you send us access. There is nothing to install, no plugin, and no server. If pasting one line is a problem, say so and we do that part too.",
  },
  {
    q: "What does it cost when I grow?",
    a: "$39 a month for the website agent, $99 with your social channels and the content factory. Both are flat: the price does not climb with the number of conversations. If you outgrow that, the third plan is priced after a call, not by a formula on a page.",
  },
  {
    q: "What happens to my customers if you disappear?",
    a: "A fair question and most companies dodge it. Your data is yours and exportable at any moment, so you leave with everything. The agent lives on one line of code you can delete in ten seconds — nothing is buried in your site. We are small and honest about it, which is exactly why nothing here locks you in.",
  },
  {
    q: "Can I read what it says, and stop it if I do not like it?",
    a: "Every conversation, in full, in your workspace. Every scheduled post before it goes out, with a delete button. One switch turns off booking, another turns off posting. Nothing runs that you cannot see, and nothing is sent that you cannot cancel.",
  },
  {
    q: "How long until it actually works?",
    a: "Most sites are answering customers the same day. The slow part is you writing four honest lines about the business — prices, hours, what you do not do. The technical part takes minutes.",
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

          <h1 className={s.title}>Take your business to a new level.</h1>

          <p className={s.sub}>
            AI agents answer your customers and book them in. AI content factories run your
            social networks. Day and night, in every language.
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
          <h2 className="h2">One agent. From question to booking.</h2>
          <p className="body">
            Someone asks. The agent answers, saves their details, and books them in. That is the whole thing.
          </p>
        </div>

        <div className={s.bentoGrid}>
          <article className={`panel ${s.cell} ${s.cellWide}`}>
            <Lightning size={34} weight="fill" />
            <h3>Answer them right away.</h3>
            <p>People buy when they get an answer fast. Your agent replies in seconds, day or night.</p>
            <div className={s.talk}>
              <p>Do you install on weekends?</p>
              <p className={s.agent}>Yes. Saturday slots are open. Want me to check a time for you?</p>
              <p>Saturday morning if possible.</p>
              <p className={s.agent}>Booked for 10:00. I have sent the details to your email.</p>
            </div>
          </article>

          <article className={`panel ${s.cell} ${s.cellTint}`}>
            <CalendarCheck size={34} weight="fill" />
            <h3>Book the appointment</h3>
            <p>It takes their phone number and offers a free time, while they are still reading.</p>
            <Link href="/calendar" className={s.cellLink}>Open calendar <ArrowUpRight weight="bold" /></Link>
          </article>

          <article className={`panel ${s.cell} ${s.cellTexture}`}>
            <div className={s.texture}>
              <Strand rungs={22} radius={72} gap={20} step={22} spin={220} />
            </div>
            <ShieldCheck size={34} weight="fill" />
            <h3>All your channels in one place</h3>
            <p>Website, Messenger, Instagram and WhatsApp. One login, one list.</p>
            <Link href="/social-accounts" className={s.cellLink}>Open channels <ArrowUpRight weight="bold" /></Link>
          </article>
        </div>
      </section>

      <section className={s.trades} aria-label="Who this is for">
        <div className={s.tradesHead}>
          <h2 className="h2">The questions you get every day.</h2>
          <p className="body">
            You write four lines about your business. The agent takes it from there.
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
            <h2 className="h2">One line, and it works.</h2>
            <p className="body">
              Paste it into your website once. No plugin. Nothing else on the page changes.
              Sign in and you get the line with your own id in it.
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
          <h2 className="h2">Simple prices.</h2>
          <p className="body">Pay monthly. Start small, add channels when you need them.</p>
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

      <section className={s.factory} id="content-factory">
        <div className={s.factoryHead}>
          <p className="eyebrow">The content factory</p>
          <h2 className="h2">We post for you too.</h2>
          <p className="body">
            Up to three posts a day, written and published on their own. You do nothing.
            Most small businesses stop posting not because they run out of ideas, but because the
            shop is full and nobody has twenty minutes. Your agent writes them from the same four
            lines you already gave it.
          </p>
          <p className={s.factoryHonest}>
            One honest note about reels. Instagram and TikTok need a real video file. The agent
            writes the text and tells you what to film, but you point the phone for thirty seconds.
            We would rather say this now than let you find out later.
          </p>
        </div>

        <div className={s.factoryBody}>
          <div className={s.factoryFeed}>
            <p className={s.factoryLabel}>Written for a dental clinic that gave us four lines</p>
            {factoryPosts.map((post) => (
              <article key={post.body} className={`panel ${s.post}`}>
                <header>
                  <span className={s.postChannel}>{post.channel}</span>
                  <span className={s.postWhen}>{post.when}</span>
                </header>
                <p>{post.body}</p>
              </article>
            ))}
            <p className={s.factoryNote}>
              Nobody wrote these. Nobody picked the times either.
            </p>
          </div>

          <ul className={s.factoryRules}>
            {factoryRules.map((item) => (
              <li key={item.rule}>
                <Check weight="bold" />
                <div>
                  <b>{item.rule}</b>
                  <p>{item.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className={s.limits} id="what-we-do" aria-label="What we do">
        <div className={s.limitsHead}>
          <h2 className="h2">What we do for you.</h2>
          <p className="body">
            Six jobs, all running while you work, sleep or travel. You write four lines about
            your business. We do the rest.
          </p>
        </div>
        <div className={s.limitGrid}>
          {doing.map((job) => (
            <article key={job.title} className={`panel ${s.limit}`}>
              <ShieldCheck size={26} weight="fill" />
              <h3>{job.title}</h3>
              <p>{job.body}</p>
              <ul className={s.jobList}>
                {job.items.map((item) => (
                  <li key={item}><Check weight="bold" size={13} />{item}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className={s.faq} aria-label="Questions">
        <h2 className="h2">The questions worth asking.</h2>
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
            <h2 className="h2">We will set it up for you.</h2>
            <p className="body">
              Tell us what you do, in four lines. We build your agent, connect your channels,
              and send you one line to paste. You install nothing and set up nothing.
            </p>
            <ol className={s.ctaSteps}>
              <li><b>You send this.</b> Four lines is enough.</li>
              <li><b>We build your agent.</b> Your prices, your hours, your language.</li>
              <li><b>You paste one line.</b> Or send us the site and we do it for you.</li>
              <li><b>It starts working.</b> Usually the same day.</li>
            </ol>
            <p className={s.ctaFoot}>
              Free to try on your own site. No card needed.
            </p>
          </div>
          <div className={s.ctaForm}>
            <DemoForm />
          </div>
        </div>
      </section>

      <footer className={s.foot}>
        <div className={s.footIn}>
          <div className={s.footBrand}>
            <Link href="#top" className={s.brandLink}>
              <span className={s.mark}>AI</span>
              <span>AI FLOW</span>
            </Link>
            <p className={s.slogan}>Take your business to a new level.</p>
            <p className={s.footBlurb}>
              AI sales agents for small business. We answer your customers, save every lead, book
              appointments and post for you. Day and night, in any language.
            </p>
            <div className={s.footChannels}>
              <span><GlobeHemisphereWest weight="regular" /> Website</span>
              <span><MetaLogo weight="regular" /> Messenger</span>
              <span><InstagramLogo weight="regular" /> Instagram</span>
              <span><WhatsappLogo weight="regular" /> WhatsApp</span>
            </div>
          </div>

          <nav className={s.footCols} aria-label="Footer">
            <div>
              <h3>Product</h3>
              <Link href="#platform">Platform</Link>
              <Link href="#how-it-works">How it works</Link>
              <Link href="#content-factory">Content factory</Link>
              <Link href="#install">Install</Link>
              <Link href="#pricing">Pricing</Link>
            </div>
            <div>
              <h3>Company</h3>
              <Link href="/about">About</Link>
              <a href="https://www.facebook.com/61589383208797/" target="_blank" rel="noreferrer">Facebook</a>
              <a href="mailto:baskinltd@yahoo.com">Contact us</a>
              <Link href="/login">Sign in</Link>
            </div>
            <div>
              <h3>Legal</h3>
              <Link href="/privacy">Privacy</Link>
              <Link href="/terms">Terms</Link>
              <Link href="/refunds">Refunds</Link>
            </div>
          </nav>
        </div>

        <div className={s.footBar}>
          <span>&copy; {new Date().getFullYear()} AI FLOW. All rights reserved.</span>
          <a href="mailto:baskinltd@yahoo.com">baskinltd@yahoo.com</a>
        </div>
      </footer>

      <SalesChat />
    </main>
  );
}
