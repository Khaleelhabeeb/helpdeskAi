import {
  ArrowRight,
  ArrowUp,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  Database,
  Headset,
  Mic,
  MessagesSquare,
  Paperclip,
  Plug,
  ShieldCheck,
  Star,
  Users,
  Zap,
} from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { Logo } from '../components/Logo';

const navLinks = [
  { label: 'Product', href: '#features', menu: true },
  { label: 'Use cases', href: '#use-cases', menu: true },
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Security', href: '#security' },
];

const useCases = [
  {
    icon: Headset,
    eyebrow: 'Support',
    title: 'Resolve every ticket, instantly',
    body: 'Answer common questions in seconds and hand off the hard ones. Your customers wait less and stay happier.',
    points: ['Answers in seconds, 24/7', 'Hands off to your team with context', 'Fewer escalations, happier customers'],
  },
  {
    icon: Zap,
    eyebrow: 'Sales',
    title: 'Turn chats into customers',
    body: 'Answer product questions, qualify leads, and move buyers forward — even at 2am.',
    points: ['Instant answers to buying questions', 'Qualifies leads automatically', 'Routes hot leads to sales'],
  },
  {
    icon: BookOpen,
    eyebrow: 'Product guidance',
    title: 'Guide users without the backlog',
    body: 'Give every user a guide that knows your product inside and out — no support queue required.',
    points: ['Onboarding that scales', 'Docs-aware, step-by-step help', 'Deflects repeated questions'],
  },
];

const steps = [
  { icon: Database, title: 'Connect your knowledge', body: 'Upload files, paste text, or add a website. We handle the rest.' },
  { icon: Bot, title: 'Create your agent', body: 'Name it, pick a model, and set the tone. Branding is applied automatically.' },
  { icon: Plug, title: 'Embed it anywhere', body: 'One line of code puts a beautiful chat widget on your site.' },
  { icon: Users, title: 'Hand off to humans', body: 'Your team steps in whenever the AI needs help, with full context.' },
];

const tickets = [
  { status: 'On hold', cls: 'bg-amber-500', name: 'Mark Lee', subject: 'Integration help', preview: 'Need help setting up the webhook' },
  { status: 'On you', cls: 'bg-red-600', name: 'Lina Haddad', subject: 'Data sync failure', preview: 'Data from Sheets is not updating' },
  { status: 'New', cls: 'bg-blue-600', name: 'John Smith', subject: 'Login problem', preview: "I can't log in even after reset" },
  { status: 'New', cls: 'bg-blue-400', name: 'Jane Doe', subject: 'Payment issue', preview: 'I was charged twice this month' },
];

const models = ['Claude Fable 5', 'Gemini 3.5 Flash', 'GPT-5.6 family', 'Llama 3.1', 'Kimi K2.7'];

const trustLogos = ['Northwind', 'Acme', 'Vertex', 'Loop', 'Beacon', 'Cobalt'];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const },
};

function HeroChat() {
  return (
    <div className="relative flex h-full min-h-[460px] items-center justify-center overflow-hidden bg-ember px-6 py-16 md:min-h-[620px]">
      <div className="bg-lattice pointer-events-none absolute inset-0" aria-hidden />
      <div className="bg-grain pointer-events-none absolute inset-0 opacity-40 mix-blend-multiply" aria-hidden />
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ delay: 0.25, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="relative flex h-[380px] w-full max-w-[440px] flex-col rounded-[28px] bg-white p-5 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.35)] md:h-[420px]"
      >
        <div>
          <p className="text-[15px] text-zinc-900">Hi there! How can I help you?</p>
          <p className="mt-2 flex items-center gap-1.5 text-xs text-zinc-400">
            <Bot className="h-3.5 w-3.5" /> AI Agent
          </p>
        </div>
        <div className="mt-5 flex justify-end">
          <div className="max-w-[80%] rounded-2xl rounded-br-md bg-zinc-950 px-4 py-2.5 text-[14px] text-white">
            What's your refund policy on annual plans?
          </div>
        </div>
        <div className="mt-3">
          <p className="max-w-[88%] text-[14px] leading-relaxed text-zinc-700">
            Annual plans are fully refundable within 30 days. Want me to start one, or connect you with a teammate?
          </p>
        </div>
        <div className="mt-auto flex items-center gap-3 rounded-full border-[1.5px] border-zinc-900 py-2 pl-4 pr-2">
          <Paperclip className="h-4 w-4 shrink-0 text-zinc-400" />
          <span className="flex-1 truncate text-[14px] text-zinc-900">
            Connect me with a person<span className="ml-px inline-block h-4 w-px translate-y-0.5 animate-pulse bg-zinc-900" />
          </span>
          <Mic className="h-4 w-4 shrink-0 text-zinc-400" />
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-zinc-950 text-white">
            <ArrowUp className="h-4 w-4" />
          </span>
        </div>
      </motion.div>
    </div>
  );
}

function SectionHeading({ eyebrow, title, italic, body }: { eyebrow: string; title: string; italic: string; body?: string }) {
  return (
    <motion.div {...fadeUp} className="max-w-2xl">
      <p className="text-sm font-medium text-zinc-500">{eyebrow}</p>
      <h2 className="mt-3 text-4xl font-semibold leading-[1.05] tracking-[-0.035em] text-zinc-950 md:text-5xl">
        {title} <span className="font-display-italic text-[1.08em]">{italic}</span>
      </h2>
      {body && <p className="mt-5 text-lg leading-relaxed text-zinc-500">{body}</p>}
    </motion.div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-canvas text-zinc-900 selection:bg-ember selection:text-white">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-hairline bg-canvas/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 md:h-[72px] md:px-8">
          <Link to="/"><Logo /></Link>
          <nav className="hidden items-center gap-7 md:flex">
            {navLinks.map((link) => (
              <a key={link.href} href={link.href} className="flex items-center gap-1 text-[15px] text-zinc-700 transition-colors hover:text-zinc-950">
                {link.label}
                {link.menu && <ChevronDown className="h-3.5 w-3.5 text-zinc-400" />}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="hidden rounded-lg px-4 py-2 text-[15px] font-medium text-zinc-700 transition-colors hover:text-zinc-950 sm:block">
              Login
            </Link>
            <Link to="/login" className="rounded-lg border border-hairline bg-white px-4 py-2 text-[15px] font-medium text-zinc-950 shadow-soft transition-colors hover:bg-zinc-50">
              Start free
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Framed page: hairline gutters like Chatbase */}
        <div className="mx-auto max-w-7xl border-x border-hairline">
          {/* Hero */}
          <section className="grid lg:grid-cols-[1.15fr_1fr]">
            <div className="flex flex-col justify-center px-6 py-16 md:px-14 md:py-24">
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-wrap items-center gap-2 text-sm text-zinc-500"
              >
                <span className="flex items-center gap-0.5 text-zinc-800">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Star key={i} className="h-3.5 w-3.5 fill-current" />
                  ))}
                </span>
                <span className="font-medium text-zinc-800">4.9</span>
                <span className="h-4 w-px bg-zinc-300" />
                <span>The AI help desk teams actually like</span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                className="mt-6 text-[52px] font-semibold leading-[0.98] tracking-[-0.045em] text-zinc-950 md:text-[76px]"
              >
                Conversational <span className="font-display-italic text-[1.1em] leading-none">agents</span> for{' '}
                <span className="font-display-italic text-[1.1em] leading-none">customer</span> experience
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 }}
                className="mt-7 max-w-xl text-lg leading-relaxed text-zinc-500 md:text-xl"
              >
                AI agents trained on your knowledge that resolve support, sales, and onboarding
                questions end to end — and hand off to your team the moment it matters.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.18 }}
                className="mt-10 flex flex-wrap items-center gap-3"
              >
                <Link to="/login" className="inline-flex h-12 items-center rounded-lg bg-zinc-950 px-6 text-[15px] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.15),0_1px_2px_rgba(0,0,0,0.3)] transition-colors hover:bg-zinc-800">
                  Start free trial
                </Link>
                <a href="#how-it-works" className="inline-flex h-12 items-center rounded-lg border border-hairline bg-white px-6 text-[15px] font-medium text-zinc-950 shadow-soft transition-colors hover:bg-zinc-50">
                  See how it works
                </a>
              </motion.div>
            </div>

            <HeroChat />
          </section>

          {/* Logos */}
          <section className="border-t border-hairline px-6 py-10 md:px-14">
            <div className="flex flex-col items-center gap-6 md:flex-row md:justify-between">
              <p className="text-sm text-zinc-500">Trusted by customer-obsessed teams</p>
              <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
                {trustLogos.map((name) => (
                  <span key={name} className="text-lg font-semibold tracking-tight text-zinc-300">{name}</span>
                ))}
              </div>
            </div>
          </section>

          {/* Platform bento */}
          <section id="features" className="border-t border-hairline">
            <div className="px-6 pb-12 pt-20 md:px-14 md:pt-28">
              <SectionHeading
                eyebrow="Platform"
                title="Everything you need to run"
                italic="support on autopilot"
                body="A complete help desk where the AI does the first mile and your team handles the rest."
              />
            </div>

            <div className="grid border-t border-hairline lg:grid-cols-2">
              {/* Helpdesk */}
              <div className="border-hairline p-6 md:p-12 lg:border-r">
                <h3 className="text-2xl font-medium tracking-tight text-zinc-950">
                  Helpdesk <span className="text-zinc-400">with live handoff to your team.</span>
                </h3>
                <motion.div {...fadeUp} className="mt-8 overflow-hidden rounded-2xl border border-hairline bg-white shadow-soft">
                  <div className="border-b border-hairline px-5 py-4 text-lg font-medium text-zinc-950">Inbox</div>
                  <div className="grid grid-cols-[88px_1fr_1.6fr] gap-4 border-b border-hairline px-5 py-3 text-sm text-zinc-500">
                    <span>Status</span><span>Requester</span><span>Details</span>
                  </div>
                  {tickets.map((t) => (
                    <div key={t.name} className="grid grid-cols-[88px_1fr_1.6fr] items-center gap-4 border-b border-zinc-100 px-5 py-3.5 text-sm last:border-0">
                      <span className={`w-fit rounded-md px-2 py-0.5 text-xs font-medium text-white ${t.cls}`}>{t.status}</span>
                      <span className="truncate text-zinc-900">{t.name}</span>
                      <span className="truncate">
                        <span className="font-medium text-zinc-900">{t.subject}</span>{' '}
                        <span className="text-zinc-400">{t.preview}</span>
                      </span>
                    </div>
                  ))}
                </motion.div>
              </div>

              {/* Handoff rules */}
              <div className="border-t border-hairline p-6 md:p-12 lg:border-t-0">
                <h3 className="text-2xl font-medium tracking-tight text-zinc-950">
                  Smart escalation <span className="text-zinc-400">that knows when to step aside.</span>
                </h3>
                <motion.div {...fadeUp} className="mt-8 rounded-2xl border border-hairline bg-white p-6 shadow-soft">
                  <p className="flex items-center gap-1 text-sm text-zinc-400">Completed 3 actions <ChevronDown className="h-3.5 w-3.5" /></p>
                  <p className="mt-3 text-[15px] leading-relaxed text-zinc-800">
                    Done. Live handoff is now enabled for billing. I'll bring in a human when customers mention:
                  </p>
                  <ul className="mt-3 space-y-1.5 text-[15px] text-zinc-800">
                    {['Charges or payments', 'Refunds', 'Subscriptions', 'Payment failures', 'Sensitive account details'].map((x) => (
                      <li key={x} className="flex items-center gap-2.5">
                        <span className="h-1 w-1 rounded-full bg-zinc-800" />{x}
                      </li>
                    ))}
                  </ul>
                </motion.div>
              </div>
            </div>

            <div className="grid border-t border-hairline md:grid-cols-3">
              {/* Analytics */}
              <div className="border-hairline p-6 md:border-r md:p-10">
                <h3 className="text-xl font-medium tracking-tight text-zinc-950">
                  Analytics <span className="text-zinc-400">on topics, sentiment, and trends.</span>
                </h3>
                <motion.div {...fadeUp} className="mt-8 rounded-2xl border border-hairline bg-white p-5 shadow-soft">
                  <p className="text-sm text-zinc-500">Resolved</p>
                  <p className="text-2xl font-medium text-zinc-950">713</p>
                  <svg viewBox="0 0 200 70" className="mt-4 h-24 w-full" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="lg-area" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0" stopColor="#16a34a" stopOpacity="0.18" />
                        <stop offset="1" stopColor="#16a34a" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <path d="M0 55 L15 50 L28 54 L42 42 L55 46 L70 34 L84 38 L98 26 L112 30 L126 20 L140 24 L155 14 L170 18 L185 8 L200 10 L200 70 L0 70Z" fill="url(#lg-area)" />
                    <path d="M0 55 L15 50 L28 54 L42 42 L55 46 L70 34 L84 38 L98 26 L112 30 L126 20 L140 24 L155 14 L170 18 L185 8 L200 10" fill="none" stroke="#16a34a" strokeWidth="1.6" />
                    <path d="M0 64 L25 62 L50 63 L75 59 L100 60 L125 56 L150 58 L175 54 L200 55" fill="none" stroke="#a1a1aa" strokeWidth="1.2" />
                  </svg>
                </motion.div>
              </div>

              {/* Integrations */}
              <div className="border-t border-hairline p-6 md:border-r md:border-t-0 md:p-10">
                <h3 className="text-xl font-medium tracking-tight text-zinc-950">
                  Deploy <span className="text-zinc-400">on your site, help page, and more.</span>
                </h3>
                <motion.div {...fadeUp} className="mt-8 grid grid-cols-3 gap-3">
                  {[MessagesSquare, BookOpen, Plug, Headset, BarChart3, Users].map((Icon, i) => (
                    <div key={i} className="grid aspect-square place-items-center rounded-2xl border border-hairline bg-white shadow-soft">
                      <Icon className="h-6 w-6 text-zinc-800" strokeWidth={1.6} />
                    </div>
                  ))}
                </motion.div>
              </div>

              {/* Models */}
              <div className="border-t border-hairline p-6 md:border-t-0 md:p-10">
                <h3 className="text-xl font-medium tracking-tight text-zinc-950">
                  Playground <span className="text-zinc-400">for testing models and settings.</span>
                </h3>
                <motion.div {...fadeUp} className="mt-8 rounded-2xl border border-hairline bg-white p-2 shadow-soft">
                  {models.map((m, i) => (
                    <div key={m} className={`flex items-center justify-between rounded-lg px-3 py-2.5 text-[15px] ${i === 3 ? 'bg-zinc-100 text-zinc-950' : 'text-zinc-700'}`}>
                      <span className="flex items-center gap-2.5"><Bot className="h-4 w-4 text-zinc-400" />{m}</span>
                      {i === 3 && <Check className="h-4 w-4" />}
                    </div>
                  ))}
                </motion.div>
              </div>
            </div>
          </section>

          {/* Use cases */}
          <section id="use-cases" className="border-t border-hairline">
            <div className="px-6 pb-12 pt-20 md:px-14 md:pt-28">
              <SectionHeading
                eyebrow="Use cases"
                title="One agent,"
                italic="every conversation"
                body="Stop bolting together point tools. A single agent understands your whole business and helps everywhere your customers reach you."
              />
            </div>
            <div className="grid border-t border-hairline md:grid-cols-3">
              {useCases.map((uc, i) => (
                <motion.article
                  key={uc.title}
                  {...fadeUp}
                  transition={{ ...fadeUp.transition, delay: i * 0.06 }}
                  className="flex flex-col border-hairline p-6 md:p-10 [&:not(:last-child)]:border-b md:[&:not(:last-child)]:border-b-0 md:[&:not(:last-child)]:border-r"
                >
                  <div className="grid h-10 w-10 place-items-center rounded-xl border border-hairline bg-white shadow-soft">
                    <uc.icon className="h-5 w-5 text-zinc-900" strokeWidth={1.75} />
                  </div>
                  <p className="mt-6 text-sm text-zinc-500">{uc.eyebrow}</p>
                  <h3 className="mt-1 text-2xl font-medium tracking-tight text-zinc-950">{uc.title}</h3>
                  <p className="mt-3 flex-1 text-[15px] leading-relaxed text-zinc-500">{uc.body}</p>
                  <ul className="mt-6 space-y-2.5">
                    {uc.points.map((p) => (
                      <li key={p} className="flex items-start gap-2.5 text-[15px] text-zinc-800">
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-ember" strokeWidth={2.5} />
                        {p}
                      </li>
                    ))}
                  </ul>
                </motion.article>
              ))}
            </div>
          </section>

          {/* How it works */}
          <section id="how-it-works" className="border-t border-hairline">
            <div className="px-6 pb-12 pt-20 md:px-14 md:pt-28">
              <SectionHeading eyebrow="How it works" title="From docs to deployed agent" italic="in minutes" />
            </div>
            <div className="grid border-t border-hairline sm:grid-cols-2 lg:grid-cols-4">
              {steps.map((step, i) => (
                <motion.div
                  key={step.title}
                  {...fadeUp}
                  transition={{ ...fadeUp.transition, delay: i * 0.06 }}
                  className="border-b border-hairline p-6 sm:border-r md:p-10 lg:border-b-0 lg:last:border-r-0"
                >
                  <span className="font-display-italic text-5xl text-zinc-300">0{i + 1}</span>
                  <div className="mt-8 flex items-center gap-2.5">
                    <step.icon className="h-4 w-4 text-zinc-900" strokeWidth={2} />
                    <h3 className="text-lg font-medium tracking-tight text-zinc-950">{step.title}</h3>
                  </div>
                  <p className="mt-2 text-[15px] leading-relaxed text-zinc-500">{step.body}</p>
                </motion.div>
              ))}
            </div>
          </section>

          {/* Security */}
          <section id="security" className="border-t border-hairline p-4 md:p-6">
            <motion.div {...fadeUp} className="relative overflow-hidden rounded-2xl bg-zinc-950 p-8 text-white md:p-14">
              <div className="bg-lattice pointer-events-none absolute inset-0 opacity-40" aria-hidden />
              <div className="relative grid gap-12 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
                <div>
                  <p className="text-sm text-zinc-400">Trust & security</p>
                  <h2 className="mt-3 text-4xl font-semibold leading-[1.05] tracking-[-0.035em] md:text-5xl">
                    Your data <span className="font-display-italic text-[1.08em]">stays yours</span>
                  </h2>
                  <p className="mt-5 max-w-md text-[15px] leading-relaxed text-zinc-400 md:text-base">
                    Built for teams that take privacy seriously — signed tokens, domain controls, and GDPR erase built in.
                  </p>
                </div>
                <div className="grid gap-3">
                  {[
                    { icon: ShieldCheck, title: 'Encrypted in transit & at rest', body: 'Industry-standard encryption for every byte of your knowledge base.' },
                    { icon: Bot, title: 'Your data never trains models', body: 'Your sources belong to you — never used to train shared models.' },
                  ].map((item) => (
                    <div key={item.title} className="flex items-start gap-4 rounded-xl border border-white/10 bg-white/[0.04] p-5">
                      <item.icon className="mt-0.5 h-5 w-5 shrink-0 text-ember" strokeWidth={1.75} />
                      <div>
                        <p className="text-[15px] font-medium text-white">{item.title}</p>
                        <p className="mt-1 text-sm leading-6 text-zinc-400">{item.body}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </section>

          {/* CTA */}
          <section className="border-t border-hairline px-6 py-24 text-center md:py-32">
            <motion.h2 {...fadeUp} className="mx-auto max-w-3xl text-5xl font-semibold leading-[1] tracking-[-0.045em] text-zinc-950 md:text-7xl">
              Put an <span className="font-display-italic text-[1.1em]">agent</span> on every customer interaction
            </motion.h2>
            <motion.p {...fadeUp} className="mx-auto mt-6 max-w-xl text-lg text-zinc-500">
              Train it on your knowledge, embed it on your site, and let it run around the clock.
            </motion.p>
            <motion.div {...fadeUp} className="mt-10 flex flex-wrap items-center justify-center gap-3">
              <Link to="/login" className="group inline-flex h-12 items-center gap-2 rounded-lg bg-zinc-950 px-6 text-[15px] font-medium text-white transition-colors hover:bg-zinc-800">
                Create your agent
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link to="/login" className="inline-flex h-12 items-center rounded-lg border border-hairline bg-white px-6 text-[15px] font-medium text-zinc-950 shadow-soft transition-colors hover:bg-zinc-50">
                Sign in
              </Link>
            </motion.div>
          </section>
        </div>
      </main>

      <footer className="border-t border-hairline">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 border-x border-hairline px-6 py-10 text-sm text-zinc-500 md:flex-row md:px-14">
          <div className="flex items-center gap-3">
            <Logo />
            <span>© 2026 HelpDeskAI</span>
          </div>
          <div className="flex items-center gap-8">
            <a href="#features" className="transition-colors hover:text-zinc-950">Platform</a>
            <a href="#use-cases" className="transition-colors hover:text-zinc-950">Use cases</a>
            <a href="#security" className="transition-colors hover:text-zinc-950">Security</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
