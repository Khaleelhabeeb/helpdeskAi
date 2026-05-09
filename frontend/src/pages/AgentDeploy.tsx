import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Code2, Copy, Globe, Loader2, Mail, MessageCircle, Smartphone } from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { Agent, apiFetch } from '../lib/api';

const options = [
  {
    title: 'Chat widget',
    status: 'Available',
    icon: Code2,
    colors: 'from-blue-500 to-cyan-400 text-blue-700 bg-blue-50 border-blue-100',
    copy: 'Embed a lightweight support widget on your website.',
  },
  {
    title: 'ChatGPT style page',
    status: 'Preview',
    icon: MessageCircle,
    colors: 'from-violet-500 to-fuchsia-400 text-violet-700 bg-violet-50 border-violet-100',
    copy: 'Give customers a hosted full-screen chat page.',
  },
  {
    title: 'Email',
    status: 'Coming soon',
    icon: Mail,
    colors: 'from-amber-500 to-orange-400 text-amber-700 bg-amber-50 border-amber-100',
    copy: 'Connect this agent to your support inbox.',
  },
  {
    title: 'WhatsApp',
    status: 'Coming soon',
    icon: Smartphone,
    colors: 'from-emerald-500 to-lime-400 text-emerald-700 bg-emerald-50 border-emerald-100',
    copy: 'Reply to WhatsApp conversations with this agent.',
  },
];

export default function AgentDeploy() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError('');
      try {
        const agents = await apiFetch<Agent[]>('/agents/');
        const found = agents.find((item) => item.id === agentId) ?? null;
        if (!found) throw new Error('Agent not found');
        setAgent(found);
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

  return (
    <AppLayout>
      <div className="space-y-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <button onClick={() => navigate('/agents')} className="mb-4 inline-flex items-center gap-2 text-sm font-bold text-on-surface-variant hover:text-brand-primary">
              <ArrowLeft className="h-4 w-4" />
              Back to agents
            </button>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Deploy {agent?.name ?? 'agent'}</h1>
            <p className="mt-1 text-sm text-on-surface-variant">Choose where your agent should show up for customers.</p>
          </div>
          <Link to="/agents" className="rounded-lg border border-surface-container-highest bg-surface-container-low px-4 py-2 text-sm font-bold text-brand-primary hover:bg-surface-container">
            Open playground
          </Link>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</div>}

        {isLoading ? (
          <div className="min-h-[320px] flex items-center justify-center text-on-surface-variant">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading deploy options...
          </div>
        ) : agent && (
          <>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
              {options.map((option) => (
                <div key={option.title} className={`rounded-xl border ${option.colors.split(' ').slice(3).join(' ')} p-6 shadow-sm`}>
                  <div className={`grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br ${option.colors.split(' ').slice(0, 2).join(' ')} text-white shadow-sm`}>
                    <option.icon className="h-6 w-6" />
                  </div>
                  <div className="mt-6 flex items-center justify-between gap-3">
                    <h2 className="text-lg font-bold text-brand-primary">{option.title}</h2>
                    <span className="rounded-full bg-white/80 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">{option.status}</span>
                  </div>
                  <p className="mt-3 text-sm text-on-surface-variant">{option.copy}</p>
                </div>
              ))}
            </div>

            <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6 shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-lg font-bold text-brand-primary flex items-center gap-2"><Globe className="h-5 w-5 text-blue-500" /> Website embed</h2>
                  <p className="mt-1 text-sm text-on-surface-variant">Paste this before the closing body tag on your website.</p>
                </div>
                <button onClick={() => navigator.clipboard?.writeText(embedCode)} className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-bold text-brand-on-primary">
                  <Copy className="h-4 w-4" />
                  Copy code
                </button>
              </div>
              <pre className="mt-5 overflow-x-auto rounded-lg bg-black p-5 text-xs text-white"><code>{embedCode}</code></pre>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
