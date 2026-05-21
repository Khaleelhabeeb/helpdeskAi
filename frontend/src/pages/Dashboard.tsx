import {
  ArrowRight,
  Bot,
  Database,
  ExternalLink,
  FileText,
  Link as LinkIcon,
  Loader2,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { Agent, apiFetch, CreditsInfo, formatRelative, KnowledgeBase } from '../lib/api';

type Activity = {
  timestamp: string;
  agent_name: string;
  question?: string | null;
  response?: string | null;
};

type DashboardData = {
  agents: Agent[];
  credits: CreditsInfo | null;
  interactions: {
    total_questions: number;
    total_responses: number;
    most_active_agent: string | null;
    agent_interaction_counts: Record<string, number>;
  } | null;
  activity: {
    recent_activity: Activity[];
    peak_usage_hour: number | null;
    hourly_activity: Record<string, number>;
  } | null;
  knowledgeCount: number;
};

function AgentAvatar({ agent }: { agent: Agent }) {
  const initials = agent.name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'AI';

  return (
    <div className="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-full bg-brand-primary text-sm font-black text-brand-on-primary">
      {agent.avatar_url ? <img src={agent.avatar_url} alt="" className="h-full w-full object-cover" /> : initials}
    </div>
  );
}

function sourceLabel(sourceType: KnowledgeBase['source_type']) {
  const labels: Record<KnowledgeBase['source_type'], string> = {
    upload_pdf: 'PDF',
    upload_txt: 'Text file',
    url: 'Website',
    text: 'Text',
    other: 'File',
  };
  return labels[sourceType] ?? 'Source';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData>({
    agents: [],
    credits: null,
    interactions: null,
    activity: null,
    knowledgeCount: 0,
  });
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [knowledge, setKnowledge] = useState<KnowledgeBase[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [isKnowledgeLoading, setKnowledgeLoading] = useState(false);
  const [error, setError] = useState('');
  const [knowledgeError, setKnowledgeError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError('');
      try {
        const summary = await apiFetch<DashboardData>('/dashboard/summary');
        if (!cancelled) setData(summary);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load dashboard');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedAgent = useMemo(
    () => data.agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [data.agents, selectedAgentId]
  );

  const selectedActivity = useMemo(() => {
    if (!selectedAgent) return [];
    return (data.activity?.recent_activity ?? []).filter((activity) => activity.agent_name === selectedAgent.name);
  }, [data.activity?.recent_activity, selectedAgent]);

  useEffect(() => {
    if (!selectedAgent) {
      setKnowledge([]);
      setKnowledgeError('');
      return;
    }

    let cancelled = false;

    async function loadKnowledge() {
      setKnowledgeLoading(true);
      setKnowledgeError('');
      try {
        const sources = await apiFetch<KnowledgeBase[]>(`/kb/${selectedAgent.id}`);
        if (!cancelled) setKnowledge(sources);
      } catch (err) {
        if (!cancelled) {
          setKnowledge([]);
          setKnowledgeError(err instanceof Error ? err.message : 'Could not load knowledge base');
        }
      } finally {
        if (!cancelled) setKnowledgeLoading(false);
      }
    }

    loadKnowledge();
    return () => {
      cancelled = true;
    };
  }, [selectedAgent?.id]);

  const selectedMessages = selectedAgent
    ? data.interactions?.agent_interaction_counts[selectedAgent.name] ?? selectedActivity.length
    : 0;

  return (
    <AppLayout>
      <div className="space-y-8">
        <header>
          <h1 className="text-3xl font-bold text-brand-primary">Dashboard</h1>
          <p className="mt-1 text-sm text-on-surface-variant">Select an agent to view its knowledge base and recent conversations.</p>
        </header>

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex min-h-[260px] items-center justify-center text-on-surface-variant">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading dashboard...
          </div>
        ) : (
          <>
            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-surface-container-highest bg-surface-container-lowest p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-bold text-on-surface-variant">Active agents</p>
                    <p className="mt-2 text-3xl font-black text-brand-primary">{data.agents.length.toLocaleString()}</p>
                  </div>
                  <div className="grid h-11 w-11 place-items-center rounded-lg bg-sky-50 text-sky-700">
                    <Bot className="h-6 w-6" />
                  </div>
                </div>
              </div>

              <div className="rounded-lg border border-surface-container-highest bg-surface-container-lowest p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-bold text-on-surface-variant">Access</p>
                    <p className="mt-2 text-3xl font-black text-brand-primary">Full access</p>
                  </div>
                  <div className="grid h-11 w-11 place-items-center rounded-lg bg-emerald-50 text-emerald-700">
                    <ShieldCheck className="h-6 w-6" />
                  </div>
                </div>
              </div>
            </section>

            <section className="space-y-4">
              <h2 className="text-lg font-black text-brand-primary">Agents</h2>

              {data.agents.length === 0 ? (
                <div className="rounded-lg border border-surface-container-highest bg-surface-container-lowest p-8 text-center">
                  <Bot className="mx-auto mb-3 h-9 w-9 text-on-surface-variant" />
                  <p className="font-bold text-brand-primary">No agents yet</p>
                  <button
                    onClick={() => navigate('/agents')}
                    className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 text-sm font-bold text-brand-on-primary hover:opacity-90"
                  >
                    Create agent
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {data.agents.map((agent) => {
                    const isSelected = selectedAgentId === agent.id;
                    return (
                      <button
                        key={agent.id}
                        onClick={() => setSelectedAgentId(agent.id)}
                        className={cn(
                          'group relative min-h-[118px] overflow-hidden rounded-lg border bg-surface-container-lowest p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-primary hover:shadow-md',
                          isSelected ? 'border-brand-primary ring-2 ring-brand-primary/10' : 'border-surface-container-highest'
                        )}
                      >
                        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#d4d4d8_1px,transparent_1px)] [background-size:18px_18px]" />
                        <div className="absolute inset-0 bg-gradient-to-br from-sky-500/10 via-transparent to-emerald-500/10" />
                        <div className="relative z-10 flex items-start gap-3">
                          <AgentAvatar agent={agent} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <p className="truncate font-black text-brand-primary">{agent.name}</p>
                              <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
                            </div>
                            <p className="mt-1 text-xs font-bold text-on-surface-variant">Created {formatRelative(agent.created_at)}</p>
                          </div>
                          <ArrowRight className={cn('h-4 w-4 text-on-surface-variant transition-transform group-hover:translate-x-1', isSelected && 'text-brand-primary')} />
                        </div>
                        <div className="relative z-10 mt-4 flex items-center justify-between border-t border-surface-container-highest pt-3">
                          <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Support agent</span>
                          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-black uppercase tracking-widest text-emerald-700">Active</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>

            {!selectedAgent ? (
              data.agents.length > 0 && (
                <div className="rounded-lg border border-dashed border-surface-container-highest bg-surface-container-lowest p-8 text-center text-sm font-medium text-on-surface-variant">
                  Click an agent card to view details.
                </div>
              )
            ) : (
              <section className="space-y-4 rounded-lg border border-surface-container-highest bg-surface-container-lowest p-5 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
                    <AgentAvatar agent={selectedAgent} />
                    <div className="min-w-0">
                      <h2 className="truncate text-xl font-black text-brand-primary">{selectedAgent.name}</h2>
                      <p className="text-sm text-on-surface-variant">Agent details</p>
                    </div>
                  </div>
                  <button
                    onClick={() => navigate(`/agents?agent=${encodeURIComponent(selectedAgent.id)}`)}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 text-sm font-bold text-brand-on-primary hover:opacity-90"
                  >
                    Open full agent configurations
                    <ExternalLink className="h-4 w-4" />
                  </button>
                </div>

                {knowledgeError && (
                  <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
                    {knowledgeError}
                  </div>
                )}

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-surface-container-highest p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold text-on-surface-variant">Knowledge base</p>
                      {isKnowledgeLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin text-violet-600" />
                      ) : (
                        <div className="grid h-9 w-9 place-items-center rounded-lg bg-violet-50 text-violet-700">
                          <Database className="h-5 w-5" />
                        </div>
                      )}
                    </div>
                    <p className="mt-2 text-3xl font-black text-brand-primary">{knowledge.length.toLocaleString()}</p>
                  </div>

                  <div className="rounded-lg border border-surface-container-highest p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold text-on-surface-variant">Messages</p>
                      <div className="grid h-9 w-9 place-items-center rounded-lg bg-amber-50 text-amber-700">
                        <MessageSquare className="h-5 w-5" />
                      </div>
                    </div>
                    <p className="mt-2 text-3xl font-black text-brand-primary">{selectedMessages.toLocaleString()}</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  <section className="overflow-hidden rounded-lg border border-surface-container-highest">
                    <div className="border-b border-surface-container-highest bg-surface-container-low px-4 py-3">
                      <h3 className="font-black text-brand-primary">Knowledge base</h3>
                    </div>
                    <div className="max-h-[320px] divide-y divide-surface-container-highest overflow-y-auto">
                      {!isKnowledgeLoading && knowledge.length === 0 && (
                        <div className="px-4 py-8 text-sm text-on-surface-variant">No knowledge base sources yet.</div>
                      )}
                      {knowledge.map((source) => (
                        <div key={source.id} className="flex items-center gap-3 px-4 py-3">
                          <div className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-lg', source.source_type === 'url' ? 'bg-sky-50 text-sky-700' : 'bg-violet-50 text-violet-700')}>
                            {source.source_type === 'url' ? <LinkIcon className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-black text-brand-primary">{source.title || source.source_uri || 'Untitled source'}</p>
                            <p className="mt-1 text-xs font-bold text-on-surface-variant">
                              {sourceLabel(source.source_type)} - {source.status}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="overflow-hidden rounded-lg border border-surface-container-highest">
                    <div className="border-b border-surface-container-highest bg-surface-container-low px-4 py-3">
                      <h3 className="font-black text-brand-primary">Recent conversations</h3>
                    </div>
                    <div className="max-h-[320px] divide-y divide-surface-container-highest overflow-y-auto">
                      {selectedActivity.length === 0 && (
                        <div className="px-4 py-8 text-sm text-on-surface-variant">No recent conversations for this agent.</div>
                      )}
                      {selectedActivity.map((activity, index) => (
                        <div key={`${activity.timestamp}-${index}`} className="px-4 py-3">
                          <div className="flex items-start justify-between gap-3">
                            <p className="line-clamp-2 text-sm font-black text-brand-primary">{activity.question || 'Customer message'}</p>
                            <span className="shrink-0 text-xs font-bold text-on-surface-variant">{formatRelative(activity.timestamp)}</span>
                          </div>
                          <p className="mt-2 text-xs font-bold text-on-surface-variant">
                            {activity.response ? 'Answered' : 'Pending'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </AppLayout>
  );
}
