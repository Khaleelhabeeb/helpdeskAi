import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Bot,
  Database,
  Rocket,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { BrandLogo, integrationBrands, type BrandLogoKey } from '../components/BrandIcons';
import { Icon3D } from '../components/Icon3D';
import { Logo } from '../components/Logo';

const floatTransition = {
  duration: 5,
  repeat: Infinity,
  repeatType: 'reverse' as const,
  ease: 'easeInOut' as const,
};

const heroFloats: { brand: BrandLogoKey; size: number; className: string; delay: number }[] = [
  { brand: 'slack', size: 36, className: 'absolute left-2 top-28 hidden md:block lg:left-10', delay: 0 },
  { brand: 'whatsapp', size: 40, className: 'absolute right-4 top-36 hidden md:block lg:right-12', delay: 0.7 },
  { brand: 'web', size: 34, className: 'absolute left-[16%] top-[44%] hidden lg:block', delay: 1.4 },
];

function FloatingBrand({
  brand,
  size,
  className,
  delay,
}: {
  brand: BrandLogoKey;
  size: number;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1, y: [0, -10, 0] }}
      transition={{ ...floatTransition, delay }}
      className={className}
    >
      <BrandLogo brand={brand} size={size} className="drop-shadow-[0_8px_24px_rgba(0,0,0,0.12)]" />
    </motion.div>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-surface text-on-surface selection:bg-brand-primary selection:text-brand-on-primary">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-surface-container-highest/60 bg-surface/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6 md:px-10">
          <Logo />
          <nav className="hidden items-center gap-8 md:flex">
            <a href="#features" className="text-sm font-medium text-on-surface-variant transition-colors hover:text-brand-primary">
              Features
            </a>
            <a href="#security" className="text-sm font-medium text-on-surface-variant transition-colors hover:text-brand-primary">
              Security
            </a>
            <a href="#docs" className="text-sm font-medium text-on-surface-variant transition-colors hover:text-brand-primary">
              Documentation
            </a>
          </nav>
          <div className="flex items-center gap-4 md:gap-5">
            <Link
              to="/login"
              className="text-sm font-medium text-on-surface-variant transition-colors hover:text-brand-primary"
            >
              Sign In
            </Link>
            <Link
              to="/login"
              className="group inline-flex items-center gap-1.5 rounded-full bg-brand-primary px-5 py-2.5 text-sm font-medium text-brand-on-primary transition-all hover:opacity-90"
            >
              Get Started
              <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="relative mx-auto max-w-6xl px-6 pb-8 pt-12 md:px-10 md:pb-16 md:pt-20">
          <div className="pointer-events-none absolute left-1/2 top-0 h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-surface-container-low blur-3xl" />

          {heroFloats.map((item) => (
            <FloatingBrand key={item.className} {...item} />
          ))}

          <div className="relative mx-auto max-w-3xl text-center">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-8 inline-flex items-center gap-2 rounded-full border border-surface-container-highest bg-surface-container-lowest px-3 py-1"
            >
              <Rocket className="h-4 w-4 text-brand-primary" />
              <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
                Trained on your docs · Human handoff built-in
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="text-4xl font-bold leading-[1.08] tracking-[-0.03em] text-brand-primary md:text-6xl lg:text-7xl"
            >
              Turn your docs into a support agent that resolves tickets
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
              className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-on-surface-variant md:text-xl"
            >
              Create an AI agent trained on your PDFs, docs, and website. Embed it on
              your site with one script — get cited, accurate answers plus seamless
              handoff to your human team when it matters. No hallucinations, no dead ends.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
            >
              <Link
                to="/login"
                className="group inline-flex h-12 items-center gap-2 rounded-full bg-brand-primary px-8 text-sm font-semibold text-brand-on-primary transition-all hover:opacity-90"
              >
                Get Started
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <a
                href="#docs"
                className="inline-flex h-12 items-center rounded-full border border-surface-container-highest bg-surface-container-lowest px-8 text-sm font-medium text-brand-primary transition-colors hover:bg-surface-container-low"
              >
                View Documentation
              </a>
            </motion.div>
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
            className="font-hand pointer-events-none absolute right-6 top-[56%] hidden text-xl text-on-surface-variant lg:block xl:right-14"
          >
            faster tickets.
            <br />
            fewer escalations.
            <span className="ml-2 inline-block rotate-12 text-2xl">↘</span>
          </motion.p>

          {/* Product preview */}
          <motion.div
            initial={{ opacity: 0, y: 48 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.7 }}
            className="relative mx-auto mt-20 max-w-5xl md:mt-28"
          >
            <div className="overflow-hidden rounded-t-2xl border border-surface-container-highest bg-surface-container-lowest shadow-[0_24px_80px_rgba(0,0,0,0.06)]">
              <div className="flex h-10 items-center gap-2 border-b border-surface-container-highest bg-surface-container-low px-4">
                <div className="h-3 w-3 rounded-full bg-red-400/30" />
                <div className="h-3 w-3 rounded-full bg-yellow-400/30" />
                <div className="h-3 w-3 rounded-full bg-green-400/30" />
              </div>
              <div className="relative aspect-[16/9] overflow-hidden bg-[#09090b]">
                <img
                  src="/landing.png"
                  alt="HelpDeskAI dashboard preview"
                  className="h-full w-full object-cover opacity-60 grayscale transition-all duration-700 hover:grayscale-0"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent" />
                <div className="absolute bottom-8 left-8 space-y-2 text-left">
                  <div className="font-mono text-xs text-white/40">&gt; Initializing Autonomous Agent Cluster...</div>
                  <div className="font-mono text-xs text-emerald-400">&gt; Connection established: Slack (Webhook connected)</div>
                  <div className="font-mono text-xs text-emerald-400">&gt; Connection established: WhatsApp API (Active)</div>
                  <div className="font-mono text-xs text-emerald-400">&gt; System ready. Awaiting inquiries.</div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* Channels section */}
        <section id="features" className="border-t border-surface-container-highest bg-surface-container-lowest/50 py-20 md:py-28">
          <div className="mx-auto grid max-w-6xl items-center gap-16 px-6 md:px-10 lg:grid-cols-2 lg:gap-20">
            <motion.div
              initial={{ opacity: 0, x: -24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-on-surface-variant">
                Every channel covered
              </p>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-brand-primary md:text-4xl lg:text-[2.65rem] lg:leading-tight">
                Show up wherever your customers already are
              </h2>
              <p className="mt-5 max-w-md text-base leading-relaxed text-on-surface-variant md:text-lg">
                Slack at 11pm. WhatsApp on the commute. A quick question on your site at lunch.
                One AI agent that meets people on their terms — same tone, same answers, no
                runaround.
              </p>
              <p className="mt-4 max-w-md text-sm leading-relaxed text-on-surface-variant/80">
                Plug in once. Reply everywhere. That&apos;s it.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              className="w-full max-w-md justify-self-center lg:max-w-none lg:justify-self-end"
            >
              <div className="grid grid-cols-3 gap-x-10 gap-y-10 md:gap-x-12 md:gap-y-12">
                {integrationBrands.map((item, i) => (
                  <motion.div
                    key={`${item.brand}-${i}`}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.05 }}
                    whileHover={{ scale: 1.08, y: -3 }}
                    className="flex items-center justify-center"
                    title={item.label}
                  >
                    <BrandLogo brand={item.brand} size={44} />
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </section>

        {/* Feature cards */}
        <section className="mx-auto max-w-6xl px-6 py-20 md:px-10 md:py-28">
          <div className="mb-14 text-center md:mb-16">
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-2xl font-bold tracking-tight text-brand-primary md:text-3xl"
            >
              Support that actually gets things done
            </motion.h2>
            <motion.p
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="mx-auto mt-3 max-w-xl text-on-surface-variant"
            >
              Less copy-pasting. Fewer escalations. More happy customers.
            </motion.p>
          </div>

          <div className="grid gap-5 md:grid-cols-3 md:gap-6">
            {[
              {
                icon: Bot,
                title: 'Autonomous Support',
                desc: 'Deploy intelligent agents capable of resolving multi-step technical inquiries using deterministic logic paths.',
                from: '#3b3b3b',
                to: '#1a1a1a',
                shadow: 'rgba(0,0,0,0.2)',
              },
              {
                title: 'Multi-platform',
                desc: 'A single unified knowledge core connected seamlessly to Slack, WhatsApp, email, and live website chat widgets.',
                brands: ['slack', 'whatsapp', 'gmail', 'web'] as BrandLogoKey[],
              },
              {
                icon: BookOpen,
                title: 'Knowledge Base',
                desc: 'Ingest thousands of technical documents, API references, and past tickets. The system strictly citations its sources.',
                from: '#10b981',
                to: '#059669',
                shadow: 'rgba(16,185,129,0.3)',
              },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="group rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-8 transition-all hover:border-brand-primary/20 hover:shadow-[0_8px_40px_rgba(0,0,0,0.06)]"
              >
                <div className="mb-6 h-14 transition-transform group-hover:scale-105">
                  {'brands' in feature ? (
                    <div className="flex items-center gap-3">
                      {feature.brands.map((brand) => (
                        <BrandLogo key={brand} brand={brand} size={28} />
                      ))}
                    </div>
                  ) : (
                    <Icon3D
                      icon={feature.icon!}
                      from={feature.from!}
                      to={feature.to!}
                      shadow={feature.shadow!}
                      size="sm"
                    />
                  )}
                </div>
                <h3 className="text-xl font-bold text-brand-primary">{feature.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Security */}
        <section id="security" className="mx-auto max-w-6xl px-6 pb-20 md:px-10 md:pb-28">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="overflow-hidden rounded-3xl border border-surface-container-highest bg-[radial-gradient(circle_at_top,#f3f3f4_0,transparent_55%)] p-10 md:p-14"
          >
            <div className="grid gap-12 lg:grid-cols-[1.1fr_1fr] lg:gap-16">
              <div>
                <p className="text-xs font-black uppercase tracking-widest text-on-surface-variant">
                  Trust & security
                </p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight text-brand-primary md:text-4xl">
                  Enterprise-grade security
                </h2>
                <p className="mt-4 max-w-md text-sm leading-relaxed text-on-surface-variant md:text-base">
                  We take security and compliance seriously. Your data stays yours. Data encryption.
                  Secure integrations.
                </p>
              </div>
              <div className="grid gap-4">
                <div className="rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-5">
                  <div className="flex items-start gap-4">
                    <ShieldCheck className="mt-0.5 h-8 w-8 shrink-0 text-emerald-600" strokeWidth={1.75} />
                    <div>
                      <p className="text-sm font-black text-brand-primary">Your data stays yours</p>
                      <p className="mt-1 text-xs leading-5 text-on-surface-variant md:text-sm">
                        Only your AI agents can access its sources. They are never used to train models.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-5">
                  <div className="flex items-start gap-4">
                    <Database className="mt-0.5 h-8 w-8 shrink-0 text-sky-600" strokeWidth={1.75} />
                    <div>
                      <p className="text-sm font-black text-brand-primary">Data encryption</p>
                      <p className="mt-1 text-xs leading-5 text-on-surface-variant md:text-sm">
                        All data is encrypted at rest and in transit. We use industry-standard encryption algorithms.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        {/* CTA */}
        <section id="docs" className="border-t border-surface-container-highest py-24 md:py-32">
          <div className="mx-auto max-w-2xl px-6 text-center md:px-10">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="mb-6 flex justify-center"
            >
              <Sparkles className="h-8 w-8 text-brand-primary" strokeWidth={1.75} />
            </motion.div>
            <motion.h2
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-2xl font-bold tracking-tight text-brand-primary md:text-3xl"
            >
              Ready to automate your technical support?
            </motion.h2>
            <motion.p
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="mx-auto mt-4 max-w-xl text-on-surface-variant"
            >
              Join forward-thinking engineering teams managing thousands of inquiries.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="mt-10"
            >
              <Link
                to="/login"
                className="group inline-flex h-12 items-center gap-2 rounded-full bg-brand-primary px-8 text-sm font-semibold text-brand-on-primary transition-all hover:opacity-90"
              >
                Start Free Trial
                <ArrowUpRight className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
              </Link>
            </motion.div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 border-t border-surface-container-highest px-6 py-10 text-sm text-on-surface-variant md:flex-row md:px-10">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="font-medium">© 2026 HelpDeskAI</span>
        </div>
        <div className="flex items-center gap-8">
          <a href="#" className="transition-colors hover:text-brand-primary">Terms</a>
          <a href="#" className="transition-colors hover:text-brand-primary">Privacy</a>
          <a href="#" className="transition-colors hover:text-brand-primary">Security</a>
        </div>
      </footer>
    </div>
  );
}
