import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Code2, Copy, Mail, MessageCircle, Phone, ShoppingBag, Smartphone } from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { Agent, apiFetch } from '../lib/api';
import { cn } from '../lib/utils';

type AgentSettingsResponse = {
  widget: {
    theme: 'light' | 'dark' | 'auto';
    color: string;
    greeting: string;
    use_color_header: boolean;
  };
};

const secondaryChannels = [
  {
    title: 'Email',
    copy: 'Connect your agent to an email address and let it respond to customer messages.',
    icon: Mail,
    color: 'bg-red-500 text-white',
    action: 'Setup',
  },
  {
    title: 'Shopify',
    copy: 'Connect your agent to Shopify and help customers with order and product questions.',
    icon: ShoppingBag,
    color: 'bg-lime-500 text-white',
    action: 'Setup',
  },
  {
    title: 'Phone',
    copy: 'Let your AI agent handle inbound phone calls.',
    icon: Phone,
    color: 'bg-violet-600 text-white',
    action: 'Setup',
    badge: 'Beta',
  },
  {
    title: 'WhatsApp',
    copy: 'Reply to WhatsApp conversations with the same trained support agent.',
    icon: Smartphone,
    color: 'bg-emerald-500 text-white',
    action: 'Setup',
  },
];

function AgentInitials({ name }: { name: string }) {
  return <span className="text-xs font-black">{name.slice(0, 2).toUpperCase() || 'AI'}</span>;
}

export default function AgentDeploy() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [settings, setSettings] = useState<AgentSettingsResponse['widget'] | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError('');
      try {
        const [agents, config] = await Promise.all([
          apiFetch<Agent[]>('/agents/'),
          agentId ? apiFetch<AgentSettingsResponse>(`/agents/${agentId}/settings`).catch(() => null) : Promise.resolve(null),
        ]);
        const found = agents.find((item) => item.id === agentId) ?? null;
        if (!found) throw new Error('Agent not found');
        setAgent(found);
        setSettings(config?.widget ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not load deploy page');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [agentId]);

  const embedCode = useMemo(() => {
    if (!agent) return '';
    return `<script src="${window.location.origin}/static/widget.js" data-agent-id="${agent.id}" display-name="${agent.name}" defer></script>`;
  }, [agent]);

  const agentName = agent?.name ?? 'Agent';
  const theme = settings?.theme === 'light' ? 'light' : 'dark';
  const primaryColor = settings?.color ?? '#ffffff';
  const headerColor = settings?.use_color_header ? primaryColor : '#1d1d20';

  async function copyEmbed() {
    await navigator.clipboard?.writeText(embedCode);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  }

  return (
    <AppLayout>
      <div className="space-y-8">
        <header>
          <button onClick={() => navigate('/agents')} className="mb-6 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant hover:text-brand-primary">
            <ArrowLeft className="h-4 w-4" />
            Back to playground
          </button>
          <h1 className="text-4xl font-bold tracking-tight text-brand-primary">All channels</h1>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}

        {isLoading ? (
          <div className="min-h-[320px] rounded-xl border border-surface-container-highest bg-surface-container-lowest p-10 text-sm font-bold text-on-surface-variant">Loading channels...</div>
        ) : agent && (
          <>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
                <div className="flex h-[310px] items-end justify-center bg-gradient-to-br from-cyan-200 via-sky-300 to-blue-500 px-10 pt-10">
                  <div className={cn('h-[250px] w-full max-w-[390px] overflow-hidden rounded-t-[24px] shadow-2xl', theme === 'light' ? 'bg-white text-black' : 'bg-black text-white')}>
                    <div className="flex h-16 items-center gap-3 px-5" style={{ backgroundColor: headerColor, color: settings?.use_color_header && primaryColor.toLowerCase() === '#ffffff' ? '#111' : '#fff' }}>
                      <div className="grid h-10 w-10 place-items-center rounded-full bg-white text-black"><AgentInitials name={agentName} /></div>
                      <div className="text-sm font-bold">{agentName}</div>
                    </div>
                    <div className="p-4">
                      <div className={cn('max-w-[72%] rounded-2xl px-4 py-3 text-sm', theme === 'light' ? 'bg-zinc-100' : 'bg-zinc-900')}>Hi! What can I help you with?</div>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-6 border-t border-surface-container-highest p-8 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-brand-primary">Chat widget</h2>
                    <p className="mt-2 max-w-lg text-base font-medium text-on-surface-variant">Add a floating chat window to your site.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={copyEmbed} className="grid h-12 w-12 place-items-center rounded-lg border border-surface-container-highest bg-surface-container-low text-brand-primary hover:bg-surface-container" aria-label="Copy embed code"><Copy className="h-5 w-5" /></button>
                    <button onClick={copyEmbed} className="h-12 rounded-lg border border-surface-container-highest bg-surface-container-low px-8 text-sm font-bold text-brand-primary hover:bg-surface-container">{copied ? 'Copied' : 'Manage'}</button>
                  </div>
                </div>
              </section>

              <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-surface-container-lowest shadow-sm">
                <div className="flex h-[310px] items-end justify-center bg-gradient-to-br from-amber-300 via-yellow-200 to-orange-400 px-10 pt-8">
                  <div className="h-[250px] w-full max-w-[620px] rounded-t-[22px] bg-white shadow-2xl">
                    <div className="flex h-10 items-center gap-2 border-b border-surface-container-highest px-6">
                      <span className="h-3 w-3 rounded-full bg-red-500" />
                      <span className="h-3 w-3 rounded-full bg-amber-400" />
                      <span className="h-3 w-3 rounded-full bg-green-500" />
                    </div>
                    <div className="px-8 py-10 text-center">
                      <h2 className="text-3xl font-bold tracking-tight text-black">How can we help you today?</h2>
                      <div className="mx-auto mt-8 flex h-20 max-w-xl items-center rounded-xl border border-surface-container-highest px-6 text-left text-on-surface-variant">
                        Ask a question...
                        <ArrowLeft className="ml-auto h-5 w-5 rotate-90" />
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex flex-col gap-6 border-t border-surface-container-highest p-8 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-2xl font-bold text-brand-primary">Help page</h2>
                    <p className="mt-2 max-w-xl text-base font-medium text-on-surface-variant">ChatGPT-style help page, deployed standalone or under a path on your site.</p>
                  </div>
                  <button className="h-12 rounded-lg border border-surface-container-highest bg-surface-container-low px-9 text-sm font-bold text-brand-primary hover:bg-surface-container">Setup</button>
                </div>
              </section>
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
              {secondaryChannels.map((channel) => (
                <section key={channel.title} className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-8 shadow-sm">
                  <div className={cn('grid h-16 w-16 place-items-center rounded-xl shadow-sm', channel.color)}>
                    <channel.icon className="h-8 w-8" />
                  </div>
                  <div className="mt-10 flex items-center gap-3">
                    <h2 className="text-2xl font-bold text-brand-primary">{channel.title}</h2>
                    {channel.badge && <span className="rounded-full bg-black px-3 py-1 text-xs font-black text-white">{channel.badge}</span>}
                  </div>
                  <p className="mt-3 min-h-20 text-base font-medium leading-relaxed text-on-surface-variant">{channel.copy}</p>
                  <div className="mt-8 flex items-center gap-3">
                    <button className="grid h-12 w-12 place-items-center rounded-lg border border-surface-container-highest bg-surface-container-low text-brand-primary hover:bg-surface-container" aria-label={`${channel.title} setup`}><Code2 className="h-5 w-5" /></button>
                    <button className="h-12 flex-1 rounded-lg border border-surface-container-highest bg-surface-container-low px-5 text-sm font-bold text-brand-primary hover:bg-surface-container">{channel.action}</button>
                  </div>
                </section>
              ))}
            </div>

            <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6 shadow-sm">
              <div className="mb-4 flex items-center gap-2 text-sm font-black uppercase tracking-widest text-on-surface-variant">
                <MessageCircle className="h-4 w-4" />
                Widget embed code
              </div>
              <pre className="overflow-x-auto rounded-lg bg-black p-5 text-xs text-white"><code>{embedCode}</code></pre>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
