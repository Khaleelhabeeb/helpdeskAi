import { Inbox as InboxIcon, Loader2, RefreshCw, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { Agent, apiFetch } from '../lib/api';

type Conv = {
  id: string;
  agent_id: string;
  status: string;
  visitor_id: string;
  visitor_email?: string | null;
  assigned_human_name?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  preview?: string | null;
};

type Msg = { id: number | string; role: string; content: string; sender_type: string; created_at?: string | null };
type ConvDetail = Conv & { messages: Msg[] };

const STATUS_META: Record<string, { label: string; cls: string }> = {
  bot: { label: 'Bot', cls: 'bg-zinc-100 text-zinc-600' },
  collecting_email: { label: 'Collecting email', cls: 'bg-sky-100 text-sky-700' },
  queued: { label: 'Queued', cls: 'bg-amber-100 text-amber-700' },
  human: { label: 'With human', cls: 'bg-sky-100 text-sky-700' },
  resolved: { label: 'Resolved', cls: 'bg-emerald-100 text-emerald-700' },
};

function statusBadge(status: string) {
  const meta = STATUS_META[status] ?? { label: status, cls: 'bg-zinc-100 text-zinc-600' };
  return <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide', meta.cls)}>{meta.label}</span>;
}

export default function Inbox() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [convs, setConvs] = useState<Conv[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState('');
  const [agentId, setAgentId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConvDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    apiFetch<Agent[]>('/agents/').then(setAgents).catch(() => {});
  }, []);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (agentId) params.set('agent_id', agentId);
      params.set('limit', '50');
      const data = await apiFetch<{ conversations: Conv[]; total: number }>(`/owner/team/conversations?${params.toString()}`, { cacheMs: 0, dedupe: false });
      setConvs(data.conversations);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load conversations');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [status, agentId]);

  async function open(id: string) {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      const data = await apiFetch<ConvDetail>(`/owner/team/conversations/${id}`, { cacheMs: 0, dedupe: false });
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load conversation');
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <AppLayout>
      <div className="space-y-4">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Inbox</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              Every customer conversation across your agents, with full transcripts.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="h-9 rounded-lg border border-surface-container-highest bg-white px-3 text-xs font-semibold focus:outline-none">
              <option value="">All statuses</option>
              <option value="bot">Bot</option>
              <option value="collecting_email">Collecting email</option>
              <option value="queued">Queued</option>
              <option value="human">With human</option>
              <option value="resolved">Resolved</option>
            </select>
            <select value={agentId} onChange={(e) => setAgentId(e.target.value)} className="h-9 rounded-lg border border-surface-container-highest bg-white px-3 text-xs font-semibold focus:outline-none">
              <option value="">All agents</option>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            <button onClick={load} className="grid h-9 w-9 place-items-center rounded-lg border border-surface-container-highest bg-white text-on-surface-variant hover:text-brand-primary">
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.1fr]">
          {/* List */}
          <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-white">
            <div className="flex items-center justify-between border-b border-surface-container-highest px-4 py-3">
              <h2 className="text-sm font-bold text-brand-primary">Conversations ({total})</h2>
            </div>
            <div className="max-h-[70vh] divide-y divide-surface-container-highest overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center py-16 text-sm text-on-surface-variant">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading…
                </div>
              ) : convs.length === 0 ? (
                <div className="px-6 py-16 text-center text-sm text-on-surface-variant">
                  <InboxIcon className="mx-auto mb-2 h-8 w-8 text-zinc-300" /> No conversations for this filter.
                </div>
              ) : (
                convs.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => open(c.id)}
                    className={cn(
                      'block w-full px-4 py-3 text-left transition-colors hover:bg-zinc-50',
                      selectedId === c.id && 'bg-zinc-50 ring-1 ring-inset ring-brand-primary/20'
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="truncate text-sm font-semibold text-brand-primary">
                        {c.visitor_email || c.visitor_id}
                      </span>
                      {statusBadge(c.status)}
                    </div>
                    <p className="mt-1 truncate text-xs text-on-surface-variant">
                      {c.preview?.slice(0, 90) || 'No messages yet'}
                    </p>
                    <div className="mt-1 text-[11px] text-on-surface-variant/70">
                      {c.assigned_human_name || 'Unassigned'} · {c.updated_at ? new Date(c.updated_at).toLocaleString() : ''}
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* Detail */}
          <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-white">
            {!detail ? (
              <div className="flex h-full min-h-[300px] items-center justify-center text-sm text-on-surface-variant">
                Select a conversation to read the transcript.
              </div>
            ) : (
              <div className="flex h-full max-h-[70vh] flex-col">
                <div className="flex items-center justify-between border-b border-surface-container-highest px-4 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold text-brand-primary">
                        {detail.visitor_email || detail.visitor_id}
                      </span>
                      {statusBadge(detail.status)}
                    </div>
                    <div className="text-xs text-on-surface-variant">
                      {detail.assigned_human_name || 'Unassigned'} · {detail.id.slice(0, 8)}
                    </div>
                  </div>
                  <button onClick={() => { setDetail(null); setSelectedId(null); }} className="grid h-8 w-8 place-items-center rounded-lg border border-surface-container-highest text-on-surface-variant hover:text-brand-primary">
                    <X className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex-1 space-y-3 overflow-y-auto bg-zinc-50 p-5">
                  {detailLoading ? (
                    <div className="flex items-center justify-center py-10"><Loader2 className="h-5 w-5 animate-spin" /></div>
                  ) : detail.messages.length === 0 ? (
                    <div className="text-sm text-on-surface-variant">No messages.</div>
                  ) : (
                    detail.messages.map((m) => (
                      <div key={m.id} className={m.sender_type === 'visitor' ? 'flex justify-end' : 'flex justify-start'}>
                        <div
                          className={cn(
                            'max-w-[82%] rounded-2xl px-4 py-2.5 text-sm',
                            m.sender_type === 'visitor'
                              ? 'rounded-br-sm bg-zinc-900 text-white'
                              : m.sender_type === 'human_agent'
                                ? 'rounded-bl-sm border border-surface-container-highest bg-white shadow-sm text-on-surface'
                                : 'rounded-bl-sm bg-zinc-200 text-zinc-700'
                          )}
                        >
                          <div className="mb-1 text-[10px] font-bold uppercase tracking-wide opacity-60">{m.sender_type}</div>
                          <div className="whitespace-pre-wrap break-words">{m.content}</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </AppLayout>
  );
}
