import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, MessageSquare, CheckCircle2, Clock, Inbox, LogOut, Send, RefreshCw, User2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { API_BASE_URL } from '../../lib/api';
import { humanAgentFetch, humanAgentSignOut, HUMAN_AGENT_TOKEN_KEY, readHumanAgentUser, HUMAN_AGENT_USER_KEY } from '../../lib/humanAgentApi';

type Conv = {
  id: string;
  agent_id: string;
  visitor_id: string;
  visitor_email?: string | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
  assigned_human_agent_id?: string | null;
  assigned_human_agent_name?: string | null;
};

type Msg = {
  id: number | string;
  role: string;
  content: string;
  sender_type: string;
  created_at?: string | null;
};

type AgentOpt = { id: string; name: string; avatar_url?: string | null };

const TABS = [
  { id: 'queued', label: 'Queued', desc: 'Waiting for you' },
  { id: 'human', label: 'Active', desc: 'Claimed by you' },
  { id: 'resolved', label: 'Resolved', desc: 'Closed' },
] as const;

type TabId = typeof TABS[number]['id'];

function fmtTime(v?: string | null) {
  if (!v) return '';
  try { return new Date(v).toLocaleString(); } catch { return v; }
}

export default function HumanAgentDashboard() {
  const nav = useNavigate();
  const user = readHumanAgentUser();
  const [agents, setAgents] = useState<AgentOpt[]>([]);
  const [activeAgentId, setActiveAgentId] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>('queued');
  const [conversations, setConversations] = useState<Conv[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Conv & { messages?: Msg[] } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const selectedIdRef = useRef<string | null>(selectedId);
  useEffect(() => { selectedIdRef.current = selectedId; try { (document as any).__humanSelectedId = selectedId; } catch {} }, [selectedId]);

  const token = typeof window !== 'undefined' ? localStorage.getItem(HUMAN_AGENT_TOKEN_KEY) : null;

  useEffect(() => {
    if (!token) { nav('/human-agent/login', { replace: true }); return; }
    let cancelled = false;
    async function init() {
      try {
        const fetched = await humanAgentFetch<AgentOpt[]>('/human-agent/agents');
        if (cancelled) return;
        setAgents(fetched);
        if (fetched.length && !activeAgentId) setActiveAgentId(fetched[0].id);
        if (fetched.length === 0) setError('');
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load agents');
      }
    }
    init();
    return () => { cancelled = true; };
  }, [token]);

  async function loadConversations(silent = false) {
    if (!token) return;
    if (!silent) setLoading(true);
    if (!silent) setError('');
    try {
      const params = new URLSearchParams();
      params.set('status', tab);
      if (activeAgentId) params.set('agent_id', activeAgentId);
      params.set('limit', '50');
      const data = await humanAgentFetch<{ conversations: Conv[]; total: number }>(`/human-agent/conversations?${params.toString()}`);
      setConversations(data.conversations);
      setTotal(data.total);
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : 'Could not load conversations');
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => { loadConversations(false); }, [tab, activeAgentId]);

  // WebSocket for live updates — single connection, no flicker
  useEffect(() => {
    if (!token) return;
    const wsBase = API_BASE_URL.replace(/^http/, 'ws');
    const wsUrl = `${wsBase}/human-agent/ws?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => { setWsConnected(false); wsRef.current = null; };
    ws.onerror = () => { try { ws.close(); } catch {} };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        const currentSelected = selectedIdRef.current;
        if (msg.type === 'status_change' || msg.type === 'resolved' || msg.type === 'agent_claimed') {
          // Silent list refresh — no spinner, no detail refetch (detail status updated locally)
          loadConversations(true);
          if (currentSelected && msg.conversation_id === currentSelected) {
            setDetail((prev) => prev ? { ...prev, status: msg.status || prev.status, assigned_human_agent_id: msg.human_agent_id || prev.assigned_human_agent_id } : prev);
          }
          return;
        }
        if (msg.type === 'message' && msg.conversation_id) {
          // Update list preview silently
          setConversations((prev) => prev.map((c) => c.id === msg.conversation_id ? { ...c, updated_at: msg.created_at || new Date().toISOString() } : c));
          if (currentSelected === msg.conversation_id) {
            // Append without full refetch — instant, no flicker
            setDetail((prev) => {
              if (!prev) return prev;
              // Dedupe by content+time to avoid double-append from openConversation
              const exists = prev.messages?.some((m) => m.content === msg.content && m.created_at === msg.created_at);
              if (exists) return prev;
              return { ...prev, messages: [...(prev.messages || []), { id: msg.message_id || Date.now(), role: msg.sender_type === 'visitor' ? 'user' : 'assistant', content: msg.content, sender_type: msg.sender_type, created_at: msg.created_at }] };
            });
            setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 30);
          } else {
            // Not viewing this conv — just silent list refresh to bump preview
            loadConversations(true);
          }
        }
      } catch {}
    };
    return () => { try { ws.close(); } catch {} wsRef.current = null; setWsConnected(false); };
  }, [token]);

  async function openConversation(id: string, silent = false) {
    if (!silent) setSelectedId(id);
    setDetailLoading(true);
    setError('');
    try {
      const data = await humanAgentFetch<Conv & { messages: Msg[] }>(`/human-agent/conversations/${id}`);
      setDetail(data);
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open conversation');
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => {
    if (selectedId) messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [detail?.messages]);

  async function claim(id: string) {
    setError(''); setNotice('');
    try {
      await humanAgentFetch(`/human-agent/conversations/${id}/claim`, { method: 'POST' });
      setNotice('Conversation claimed — you can now reply.');
      setTab('human');
      // Optimistic: move conv to human in list without spinner
      setConversations((prev) => prev.map((c) => c.id === id ? { ...c, status: 'human' } : c));
      setDetail((prev) => prev && prev.id === id ? { ...prev, status: 'human' } : prev);
      loadConversations(true);
      await openConversation(id, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Claim failed');
    }
  }

  async function sendReply() {
    if (!selectedId || !reply.trim() || !detail) return;
    const content = reply.trim();
    const tempId = Date.now();
    // Optimistic append — no flicker
    setDetail((prev) => prev ? { ...prev, messages: [...(prev.messages || []), { id: tempId, role: 'assistant', content, sender_type: 'human_agent', created_at: new Date().toISOString() }] } : prev);
    setReply('');
    setSending(true); setError('');
    try {
      await humanAgentFetch<{ id: number; created_at: string }>(`/human-agent/conversations/${selectedId}/messages`, { method: 'POST', body: JSON.stringify({ content }) });
      // Keep optimistic message; just bump list preview silently
      setConversations((prev) => prev.map((c) => c.id === selectedId ? { ...c, updated_at: new Date().toISOString() } : c));
      setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 30);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Send failed');
      // Rollback optimistic on error
      setDetail((prev) => prev ? { ...prev, messages: prev.messages?.filter((m) => m.id !== tempId) } : prev);
      setReply(content);
    } finally {
      setSending(false);
    }
  }

  async function resolve() {
    if (!selectedId) return;
    if (!confirm('Mark this conversation as resolved?')) return;
    setError(''); setNotice('');
    try {
      await humanAgentFetch(`/human-agent/conversations/${selectedId}/resolve`, { method: 'POST' });
      setNotice('Conversation resolved');
      setDetail((prev) => prev ? { ...prev, status: 'resolved' } : prev);
      setConversations((prev) => prev.map((c) => c.id === selectedId ? { ...c, status: 'resolved' } : c));
      loadConversations(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resolve failed');
    }
  }

  function signOut() {
    humanAgentSignOut();
    try { wsRef.current?.close(); } catch {}
    nav('/human-agent/login', { replace: true });
  }

  const emptyState = useMemo(() => {
    if (agents.length === 0) {
      return {
        title: "You haven't been assigned to any AI agent yet",
        body: "Ask your account owner to assign you to an AI agent so you can see incoming chats.",
      };
    }
    if (conversations.length === 0 && !loading) {
      const tabLabel = TABS.find((t) => t.id === tab)?.label || tab;
      return { title: `No ${tabLabel.toLowerCase()} conversations`, body: tab === 'queued' ? "Queued conversations assigned to your AI agents will appear here." : tab === 'human' ? "Claim a queued conversation to see it here." : "Resolved conversations will appear here." };
    }
    return null;
  }, [agents.length, conversations.length, loading, tab]);

  return (
    <div className="h-screen bg-[#f8f8f7] flex flex-col overflow-hidden">
      <header className="h-14 border-b border-zinc-200 bg-white flex items-center justify-between px-4 md:px-6 shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-black text-white grid place-items-center font-bold text-sm">H</div>
          <div>
            <div className="text-sm font-bold text-zinc-900">Human Agent</div>
            <div className="text-xs text-zinc-500 flex items-center gap-2">
              <span>{user?.email}</span>
              <span className={cn('inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border', wsConnected ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-zinc-200 bg-zinc-50 text-zinc-500')}>
                <span className={cn('w-1.5 h-1.5 rounded-full', wsConnected ? 'bg-emerald-500' : 'bg-zinc-400')} />{wsConnected ? 'Live' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => loadConversations()} className="h-8 w-8 grid place-items-center rounded-lg border border-zinc-200 bg-zinc-50 hover:bg-white text-zinc-600"><RefreshCw className="w-4 h-4" /></button>
          <button onClick={signOut} className="h-8 px-3 rounded-lg border border-zinc-200 bg-white text-xs font-bold hover:bg-zinc-50 flex items-center gap-1.5"><LogOut className="w-3.5 h-3.5" /> Sign out</button>
        </div>
      </header>

      {(error || notice) && (
        <div className={cn('mx-4 md:mx-6 mt-4 rounded-xl border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>{error || notice}</div>
      )}

      {/* Agent switcher */}
      <div className="px-4 md:px-6 pt-4">
        {agents.length > 0 ? (
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
            {agents.map((ag) => (
              <button key={ag.id} onClick={() => setActiveAgentId(ag.id)} className={cn('shrink-0 flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold', activeAgentId === ag.id ? 'bg-black text-white border-black' : 'bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50')}>
                <span className="w-7 h-7 rounded-lg bg-zinc-100 grid place-items-center overflow-hidden text-xs font-bold">
                  {ag.avatar_url ? <img src={ag.avatar_url} alt="" className="w-full h-full object-cover" /> : ag.name.slice(0,2).toUpperCase()}
                </span>
                {ag.name}
              </button>
            ))}
            <button onClick={() => setActiveAgentId(null)} className={cn('shrink-0 rounded-xl border px-3 py-2 text-sm font-semibold', !activeAgentId ? 'bg-black text-white border-black' : 'bg-white border-zinc-200 text-zinc-600')}>All agents</button>
          </div>
        ) : (
          <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">You haven't been assigned to any AI agent yet — ask your account owner to assign you.</div>
        )}
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4 p-4 md:p-6 max-w-[1600px] mx-auto w-full min-h-0 h-[calc(100vh-180px)] lg:h-[calc(100vh-160px)]">
        {/* Left: tabs + list — scrolls inside, not page */}
        <div className="bg-white rounded-2xl border border-zinc-200 overflow-hidden flex flex-col min-h-0 h-full">
          <div className="grid grid-cols-3 border-b border-zinc-200">
            {TABS.map((t) => (
              <button key={t.id} onClick={() => setTab(t.id)} className={cn('py-3 text-center border-b-2 transition-colors', tab === t.id ? 'border-black bg-zinc-50 text-zinc-900' : 'border-transparent text-zinc-500 hover:text-zinc-900 hover:bg-zinc-50/50')}>
                <div className="text-sm font-bold">{t.label}</div>
                <div className="text-[10px] uppercase tracking-widest font-bold opacity-60">{t.desc}</div>
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-zinc-100 min-h-0">
            {loading ? (
              <div className="p-10 flex items-center justify-center text-sm text-zinc-500"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
            ) : emptyState ? (
              <div className="p-10 text-center">
                <div className="mx-auto w-12 h-12 rounded-2xl bg-zinc-900 text-white grid place-items-center"><Inbox className="w-6 h-6" /></div>
                <p className="mt-3 font-bold text-zinc-900">{emptyState.title}</p>
                <p className="text-sm text-zinc-500 mt-1">{emptyState.body}</p>
              </div>
            ) : (
              conversations.map((c) => (
                <button key={c.id} onClick={() => openConversation(c.id)} className={cn('w-full text-left p-4 hover:bg-zinc-50 transition-colors', selectedId === c.id && 'bg-zinc-900 text-white hover:bg-zinc-900')}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className={cn('text-sm font-semibold truncate', selectedId === c.id ? 'text-white' : 'text-zinc-900')}>{c.visitor_email || c.visitor_id}</div>
                      <div className={cn('text-xs truncate flex items-center gap-1.5 mt-0.5', selectedId === c.id ? 'text-zinc-300' : 'text-zinc-500')}>
                        {c.status === 'queued' ? <Clock className="w-3 h-3" /> : c.status === 'human' ? <MessageSquare className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                        {c.status} · {fmtTime(c.updated_at)}
                      </div>
                    </div>
                    <span className={cn('text-[10px] font-black uppercase tracking-widest px-1.5 py-1 rounded border shrink-0',
                      c.status === 'queued' ? 'bg-amber-50 border-amber-200 text-amber-700' :
                      c.status === 'human' ? 'bg-sky-50 border-sky-200 text-sky-700' :
                      'bg-zinc-100 border-zinc-200 text-zinc-600'
                    )}>{c.status}</span>
                  </div>
                  <div className={cn('text-xs mt-1 line-clamp-1', selectedId === c.id ? 'text-zinc-300' : 'text-zinc-500')}>
                    {c.id.slice(0,8)}… · agent {c.agent_id.slice(0,6)}
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="p-3 border-t border-zinc-200 text-xs text-zinc-500 flex items-center justify-between">
            <span>{total} total</span>
            <span className="flex items-center gap-1"><User2 className="w-3 h-3" />{user?.name || user?.email}</span>
          </div>
        </div>

        {/* Right: conversation view — messages scroll inside */}
        <div className="bg-white rounded-2xl border border-zinc-200 overflow-hidden flex flex-col min-h-0 h-full">
          {!selectedId || !detail ? (
            <div className="flex-1 grid place-items-center p-8 text-center">
              <div>
                <div className="mx-auto w-12 h-12 rounded-2xl bg-zinc-100 grid place-items-center text-zinc-500"><MessageSquare className="w-6 h-6" /></div>
                <p className="mt-3 font-semibold text-zinc-900">Select a conversation</p>
                <p className="text-sm text-zinc-500">Choose a conversation on the left to read and reply.</p>
              </div>
            </div>
          ) : detailLoading ? (
            <div className="flex-1 grid place-items-center text-sm text-zinc-500"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
          ) : (
            <>
              <div className="px-4 md:px-6 py-4 border-b border-zinc-200 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-bold text-zinc-900 flex items-center gap-2">
                    {detail.visitor_email || detail.visitor_id}
                    <span className={cn('text-[10px] font-black uppercase tracking-widest px-1.5 py-0.5 rounded border',
                      detail.status === 'queued' ? 'bg-amber-50 border-amber-200 text-amber-700' :
                      detail.status === 'human' ? 'bg-sky-50 border-sky-200 text-sky-700' :
                      'bg-zinc-100 border-zinc-200 text-zinc-600'
                    )}>{detail.status}</span>
                  </div>
                  <div className="text-xs text-zinc-500">Visitor {detail.visitor_id} · {fmtTime(detail.created_at)} · {detail.visitor_email || 'no email'}</div>
                </div>
                <div className="flex items-center gap-2">
                  {detail.status === 'queued' && <button onClick={() => claim(detail.id)} className="h-9 px-4 rounded-xl bg-black text-white text-xs font-bold hover:bg-zinc-800">Claim</button>}
                  {(detail.status === 'human' || detail.status === 'queued') && <button onClick={resolve} className="h-9 px-4 rounded-xl border border-zinc-200 bg-white text-xs font-bold hover:bg-zinc-50 flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Resolve</button>}
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-3 bg-[#fcfcfc] min-h-0">
                {(detail.messages || []).length === 0 ? (
                  <div className="text-sm text-zinc-500">No messages yet.</div>
                ) : (
                  (detail.messages || []).map((m) => {
                    const isHuman = m.sender_type === 'human_agent';
                    const isVisitor = m.sender_type === 'visitor';
                    const isSystem = m.sender_type === 'system';
                    const isYou = isHuman; // you are the human agent
                    if (isSystem) return <div key={m.id} className="text-center"><span className="inline-block text-xs bg-zinc-100 border border-zinc-200 rounded-full px-3 py-1 text-zinc-600">{m.content}</span></div>;
                    return (
                      <div key={m.id} className={cn('flex', isYou ? 'justify-end' : 'justify-start')}>
                        <div className={cn('max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
                          isYou ? 'bg-zinc-900 text-white rounded-br-sm shadow-sm' :
                          isVisitor ? 'bg-white border border-zinc-200 text-zinc-900 rounded-bl-sm shadow-sm' :
                          'bg-zinc-100 text-zinc-900 border border-zinc-200'
                        )}>
                          <div className={cn('text-[10px] font-bold tracking-widest uppercase mb-1', isYou ? 'text-zinc-400' : 'text-zinc-500')}>{isYou ? 'You' : isVisitor ? 'Visitor' : m.sender_type}</div>
                          <div className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</div>
                          <div className={cn('text-[10px] mt-1.5', isYou ? 'text-zinc-400' : 'text-zinc-500')}>{fmtTime(m.created_at)}</div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              <div className="p-4 border-t border-zinc-200 bg-white">
                {detail.status === 'resolved' ? (
                  <div className="rounded-xl bg-zinc-100 border border-zinc-200 px-4 py-3 text-sm text-zinc-600 text-center">This conversation is resolved — read-only.</div>
                ) : detail.status !== 'human' ? (
                  <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800 text-center">Claim the conversation to reply.</div>
                ) : (
                  <div className="flex gap-3">
                    <textarea value={reply} onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendReply(); } }} rows={2} placeholder="Type your reply…" className="flex-1 resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm focus:bg-white focus:border-zinc-300 focus:outline-none" />
                    <button onClick={sendReply} disabled={sending || !reply.trim()} className="self-end h-11 px-5 rounded-xl bg-black text-white text-sm font-bold hover:bg-zinc-800 disabled:opacity-50 flex items-center gap-2">
                      {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}Send
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
