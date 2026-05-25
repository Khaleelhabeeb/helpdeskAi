import { Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, CheckCircle2, Code2, Globe, Shield } from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { API_BASE_URL } from '../lib/api';

const exampleSnippet = `<script
  src="${API_BASE_URL}/static/widget.js"
  data-deployment-id="YOUR_DEPLOYMENT_ID"
  defer
></script>`;

const steps = [
  {
    title: 'Copy your embed snippet',
    body: 'Open your agent’s Deploy → Chat widget page, then copy the embed code shown under Allowed domains.',
  },
  {
    title: 'Paste it on your website',
    body: 'Add the script tag to every page where you want the chat bubble. Place it just before the closing </body> tag.',
  },
  {
    title: 'Publish and test',
    body: 'Save your site, open it in the browser, and confirm the widget loads. Send a test message to verify the agent responds.',
  },
  {
    title: 'Allow your domain',
    body: 'In widget settings, add each live domain (e.g. example.com) under Allowed domains. The widget only works on domains you list.',
  },
];

export default function Guides() {
  return (
    <AppLayout>
      <div className="mx-auto max-w-3xl space-y-10">
        <header>
          <Link
            to="/agents"
            className="mb-4 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant transition-colors hover:text-brand-primary"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to agents
          </Link>
          <div className="flex items-start gap-4">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-brand-primary text-brand-on-primary">
              <BookOpen className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Embedding guide</h1>
              <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                Add the HelpDeskAI chat widget to any site in a few minutes. No framework required—just one script tag.
              </p>
            </div>
          </div>
        </header>

        <section className="space-y-4">
          {steps.map((step, index) => (
            <article
              key={step.title}
              className="flex gap-4 rounded-xl border border-surface-container-highest bg-surface-container-lowest p-5 shadow-sm"
            >
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-primary text-sm font-black text-brand-on-primary">
                {index + 1}
              </span>
              <div>
                <h2 className="font-bold text-brand-primary">{step.title}</h2>
                <p className="mt-1 text-sm leading-relaxed text-on-surface-variant">{step.body}</p>
              </div>
            </article>
          ))}
        </section>

        <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2 text-sm font-bold text-brand-primary">
            <Code2 className="h-4 w-4" />
            Example snippet
          </div>
          <pre className="overflow-x-auto rounded-lg bg-zinc-950 p-4 text-xs leading-relaxed text-zinc-100">
            <code>{exampleSnippet}</code>
          </pre>
          <p className="mt-3 text-xs text-on-surface-variant">
            Replace <span className="font-mono font-semibold">YOUR_DEPLOYMENT_ID</span> with the ID from your agent’s embed code, or copy the full snippet from Deploy so it’s already filled in.
          </p>
        </section>

        <section className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-surface-container-highest bg-surface-container-low p-5">
            <div className="flex items-center gap-2 font-bold text-brand-primary">
              <Globe className="h-4 w-4" />
              Where to put it
            </div>
            <ul className="mt-3 space-y-2 text-sm text-on-surface-variant">
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                Marketing site, docs, or app shell
              </li>
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                WordPress, Webflow, Shopify theme (footer / custom code)
              </li>
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                React / Next.js: root layout or <span className="font-mono text-xs">index.html</span>
              </li>
            </ul>
          </div>
          <div className="rounded-xl border border-surface-container-highest bg-surface-container-low p-5">
            <div className="flex items-center gap-2 font-bold text-brand-primary">
              <Shield className="h-4 w-4" />
              Domains & security
            </div>
            <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">
              List every hostname that will show the widget. Use <span className="font-mono text-xs">localhost</span> while developing. Subdomains of an allowed domain are accepted automatically.
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
          <p className="font-bold">Widget not showing?</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-amber-800/90">
            <li>Confirm the script is on the published page (not only in draft preview).</li>
            <li>Check the browser console for blocked scripts or ad blockers.</li>
            <li>Make sure your site’s domain is added under Allowed domains and settings are saved.</li>
          </ul>
        </section>
      </div>
    </AppLayout>
  );
}
