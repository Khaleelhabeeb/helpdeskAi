import {
  ArrowRight,
  BarChart3,
  Bot,
  Database,
  Inbox,
  Loader2,
  MessageSquare,
  Plus,
  Rocket,
  UserPlus,
  Users,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { Agent, apiFetch, formatRelative } from '../lib/api';

type Activity = {
  timestamp: string;
  agent_name: string;
  question?: string | null;
  response?: string | null;
};

type DashboardData = {
  agents: Agent[];
  credits: { agent_usage: Array<{ agent_id: string; agent_name: string; credits_used: number }> } | null;
  interactions: { total_questions: number; most_active_agent: string | null; agent_interaction_counts: Record<string, number> } | null;
  activity: { recent_activity: Activity[] } | null;
  knowledgeCount: number;
};

type TeamAnalytics = { total: number; queued: number; human: number; resolved: number };

function AgentAvatar({ agent }: { agent: Agent }) {
  const initials =
    agent.name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'AI';
  return (
    <div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl bg-zinc-900 text-sm font-semibold text-white">
      {agent.avatar_url ? <img src={agent.avatar_url} alt="" className="h-full w-full object-cover" /> : initials}
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [team, setTeam] = useState<TeamAnalytics | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError('');
      try {
        const summary = await apiFetch<DashboardData>('/dashboard/summary');
        if (cancelled) return;
        setData(summary);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load dashboard');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch<TeamAnalytics>('/owner/team/analytics', { cacheMs: 0, dedupe: false })
      .then((t) => { if (!cancelled) setTeam(t); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const stats = useMemo(() => {
    const agents = data?.agents ?? [];
    const totalMessages = data?.interactions?.total_questions ?? 0;
    return [
      { icon: Bot, label: 'Agents', value: agents.length.toLocaleString(), to: '/agents' },
      { icon: Database, label: 'Knowledge sources', value: (data?.knowledgeCount ?? 0).toLocaleString(), to: '/knowledge' },
      { icon: MessageSquare, label: 'Conversations', value: (team?.total ?? totalMessages).toLocaleString(), to: '/inbox' },
      { icon: Users, label: 'Queued for humans', value: (team?.queued ?? 0).toLocaleString(), to: '/inbox' },
    ];
  }, [data, team]);

  const quickActions = [
    { icon: Plus, label: 'Create agent', desc: 'Train an agent on your content', to: '/agents', primary: true },
    { icon: Database, label: 'Add knowledge', desc: 'PDFs, text, or websites', to: '/knowledge', primary: false },
    { icon: UserPlus, label: 'Invite teammate', desc: 'Add a human agent', to: '/team', primary: false },
    { icon: Rocket, label: 'Deploy widget', desc: 'Embed chat on your site', to: '/agents', primary: false },
  ];

  return (
    <AppLayout>
      <div className="space-y-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Overview</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              Everything in your workspace, in one place.
            </p>
          </div>
          <Link
            to="/agents"
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-brand-primary px-5 text-sm font-semibold text-brand-on-primary transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> Create agent
          </Link>
        </header>

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
        )}

        {isLoading ? (
          <div className="flex min-h-[260px] items-center justify-center text-sm text-on-surface-variant">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading overview...
          </div>
        ) : (
          <>
            {/* Stat cards */}
            <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {stats.map((s) => (
                <Link
                  key={s.label}
                  to={s.to}
                  className="group rounded-xl border border-surface-container-highest bg-white p-5 transition-all hover:border-zinc-300 hover:shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="grid h-9 w-9 place-items-center rounded-lg bg-zinc-100 text-zinc-600 transition-colors group-hover:bg-brand-primary group-hover:text-white">
                      <s.icon className="h-5 w-5" strokeWidth={2} />
                    </div>
                    <ArrowRight className="h-4 w-4 text-zinc-300 transition-all group-hover:translate-x-0.5 group-hover:text-zinc-500" />
                  </div>
                  <p className="mt-4 text-3xl font-bold text-brand-primary">{s.value}</p>
                  <p className="mt-1 text-sm text-on-surface-variant">{s.label}</p>
                </Link>
              ))}
            </section>

            {/* Quick actions */}
            <section>
              <h2 className="mb-3 text-lg font-semibold text-brand-primary">Quick actions</h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {quickActions.map((a) => (
                  <Link
                    key={a.label}
                    to={a.to}
                    className={cn(
                      'group flex items-center gap-3 rounded-xl border p-4 transition-all hover:shadow-sm',
                      a.primary
                        ? 'border-brand-primary bg-brand-primary text-brand-on-primary hover:opacity-95'
                        : 'border-surface-container-highest bg-white hover:border-zinc-300'
                    )}
                  >
                    <span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-lg', a.primary ? 'bg-white/15 text-white' : 'bg-zinc-100 text-zinc-600 group-hover:bg-brand-primary group-hover:text-white transition-colors')}>
                      <a.icon className="h-5 w-5" strokeWidth={2} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold">{a.label}</span>
                      <span className={cn('block text-xs', a.primary ? 'text-white/70' : 'text-on-surface-variant')}>{a.desc}</span>
                    </span>
                  </Link>
                ))}
              </div>
            </section>

            {/* Agents */}
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-brand-primary">Your agents</h2>
                <Link to="/agents" className="inline-flex items-center gap-1 text-sm font-semibold text-zinc-900 hover:text-zinc-600">
                  Manage <ArrowRight className="h-4 w-4" />
                </Link>
              </div>

              {!data || data.agents.length === 0 ? (
                <div className="rounded-xl border border-dashed border-surface-container-highest bg-white p-10 text-center">
                  <Bot className="mx-auto mb-3 h-10 w-10 text-zinc-300" strokeWidth={1.5} />
                  <p className="font-semibold text-brand-primary">No agents yet</p>
                  <p className="mt-1 text-sm text-on-surface-variant">
                    Create your first agent to start handling customer conversations.
                  </p>
                  <button
                    onClick={() => navigate('/agents')}
                    className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 text-sm font-semibold text-brand-on-primary hover:opacity-90"
                  >
                    Create agent <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {data.agents.map((agent) => {
                    const messages = data.interactions?.agent_interaction_counts[agent.name] ?? 0;
                    return (
                      <div
                        key={agent.id}
                        className="flex flex-col rounded-xl border border-surface-container-highest bg-white p-5 transition-all hover:border-zinc-300 hover:shadow-sm"
                      >
                        <div className="flex items-center gap-3">
                          <AgentAvatar agent={agent} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-semibold text-brand-primary">{agent.name}</p>
                            <p className="text-xs text-on-surface-variant">Created {formatRelative(agent.created_at)}</p>
                          </div>
                        </div>
                        <div className="mt-4 flex items-center gap-2 text-xs text-on-surface-variant">
                          <MessageSquare className="h-3.5 w-3.5" /> {messages.toLocaleString()} messages
                        </div>
                        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-surface-container-highest pt-4">
                          <button
                            onClick={() => navigate(`/agents?agent=${encodeURIComponent(agent.id)}`)}
                            className="inline-flex items-center justify-center gap-1 rounded-lg border border-surface-container-highest px-2 py-2 text-xs font-semibold text-brand-primary transition-colors hover:bg-zinc-50"
                          >
                            Playground
                          </button>
                          <Link
                            to={`/knowledge?agent=${encodeURIComponent(agent.id)}`}
                            className="inline-flex items-center justify-center gap-1 rounded-lg border border-surface-container-highest px-2 py-2 text-xs font-semibold text-brand-primary transition-colors hover:bg-zinc-50"
                          >
                            Sources
                          </Link>
                          <Link
                            to={`/agents/${agent.id}/deploy`}
                            className="inline-flex items-center justify-center gap-1 rounded-lg border border-surface-container-highest px-2 py-2 text-xs font-semibold text-brand-primary transition-colors hover:bg-zinc-50"
                          >
                            Deploy
                          </Link>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Recent activity */}
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-brand-primary">Recent activity</h2>
                <Link to="/analytics" className="inline-flex items-center gap-1 text-sm font-semibold text-zinc-900 hover:text-zinc-600">
                  <BarChart3 className="h-4 w-4" /> Analytics
                </Link>
              </div>
              <div className="overflow-hidden rounded-xl border border-surface-container-highest bg-white">
                {(data.activity?.recent_activity ?? []).length === 0 ? (
                  <div className="px-6 py-10 text-center text-sm text-on-surface-variant">
                    <Inbox className="mx-auto mb-2 h-6 w-6 text-zinc-300" /> No activity yet.
                  </div>
                ) : (
                  <div className="divide-y divide-surface-container-highest">
                    {data.activity!.recent_activity.slice(0, 6).map((a, i) => (
                      <div key={`${a.timestamp}-${i}`} className="flex items-start justify-between gap-4 px-5 py-3.5">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-brand-primary">{a.question || 'Customer message'}</p>
                          <p className="text-xs text-on-surface-variant">{a.agent_name} · {a.response ? 'Answered' : 'Pending'}</p>
                        </div>
                        <span className="shrink-0 text-xs text-on-surface-variant">{formatRelative(a.timestamp)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  );
}
