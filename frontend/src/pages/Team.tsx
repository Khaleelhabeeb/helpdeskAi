import { useEffect, useState } from 'react';
import { AppLayout } from '../components/Layout';
import { apiFetch, Agent } from '../lib/api';
import { Loader2, UserPlus, Mail, Shield, Trash2, Send, Check, X, ExternalLink, Copy, BarChart3, Clock, MessageSquare, CheckCircle2, Users, Eye } from 'lucide-react';
import { cn } from '../lib/utils';

type HumanAgent = {
  id: string;
  email: string;
  name?: string | null;
  status: string;
  created_at?: string | null;
  assignments: string[];
  invite_token?: string;
  invite_link?: string;
};

type Analytics = {
  total: number;
  by_status: Record<string, number>;
  cases_closed: number;
  active: number;
  queued: number;
  human: number;
  by_human: Array<{ id: string; email: string; name?: string | null; status: string; total: number; queued: number; human: number; resolved: number; collecting_email: number }>;
  by_agent: Array<{ id: string; name: string; total: number; by_status: Record<string, number> }>;
  recent: Array<{ id: string; agent_id: string; status: string; visitor_id: string; visitor_email?: string | null; assigned_human_name?: string | null; updated_at?: string | null }>;
};

type TeamConv = {
  id: string;
  agent_id: string;
  status: string;
  visitor_id: string;
  visitor_email?: string | null;
  assigned_human_name?: string | null;
  assigned_human_agent_id?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  preview?: string | null;
};

type ConvDetail = {
  id: string;
  agent_id: string;
  status: string;
  visitor_id: string;
  visitor_email?: string | null;
  assigned_human_name?: string | null;
  messages: Array<{ id: number | string; content: string; sender_type: string; created_at?: string | null }>;
};

export default function Team() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [humanAgents, setHumanAgents] = useState<HumanAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviting, setInviting] = useState(false);
  const [selectedAssignments, setSelectedAssignments] = useState<Record<string, string[]>>({});
  const [savingAssignments, setSavingAssignments] = useState<string | null>(null);

  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [aLoading, setALoading] = useState(true);
  const [convs, setConvs] = useState<TeamConv[]>([]);
  const [cTotal, setCTotal] = useState(0);
  const [cLoading, setCLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterAgent, setFilterAgent] = useState<string>('');
  const [selectedConv, setSelectedConv] = useState<ConvDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [ha, ag] = await Promise.all([
        apiFetch<HumanAgent[]>('/owner/human-agents', { cacheMs: 0, dedupe: false }),
        apiFetch<Agent[]>('/agents/', { cacheMs: 0, dedupe: false }),
      ]);
      setHumanAgents(ha);
      setAgents(ag);
      const map: Record<string, string[]> = {};
      ha.forEach((h) => (map[h.id] = h.assignments || []));
      setSelectedAssignments(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load team');
    } finally {
      setLoading(false);
    }
  }

  async function loadAnalytics() {
    setALoading(true);
    try {
      const data = await apiFetch<Analytics>('/owner/team/analytics', { cacheMs: 0, dedupe: false });
      setAnalytics(data);
    } catch (e) {
    } finally {
      setALoading(false);
    }
  }

  async function loadConvs() {
    setCLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set('status', filterStatus);
      if (filterAgent) params.set('agent_id', filterAgent);
      params.set('limit', '30');
      const data = await apiFetch<{ conversations: TeamConv[]; total: number }>(`/owner/team/conversations?${params.toString()}`, { cacheMs: 0, dedupe: false });
      setConvs(data.conversations);
      setCTotal(data.total);
    } catch (e) {
    } finally {
      setCLoading(false);
    }
  }

  useEffect(() => { load(); loadAnalytics(); }, []);
  useEffect(() => { loadConvs(); }, [filterStatus, filterAgent]);

  async function invite() {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError(''); setNotice('');
    try {
      const res = await apiFetch<HumanAgent>('/owner/human-agents', {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail.trim().toLowerCase(), name: inviteName.trim() || undefined }),
      });
      setNotice(`Invite sent to ${res.email}${res.invite_link ? ' — link below (dev).' : ''}`);
      setInviteEmail(''); setInviteName('');
      await load(); await loadAnalytics();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Invite failed');
    } finally {
      setInviting(false);
    }
  }

  async function saveAssignments(haId: string) {
    const ids = selectedAssignments[haId] || [];
    setSavingAssignments(haId);
    setError(''); setNotice('');
    try {
      const updated = await apiFetch<HumanAgent>(`/owner/human-agents/${haId}/assignments`, {
        method: 'PATCH',
        body: JSON.stringify({ agent_ids: ids }),
      });
      setHumanAgents((prev) => prev.map((h) => h.id === haId ? updated : h));
      setNotice(`Assignments updated for ${updated.email}`);
      loadAnalytics();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update assignments');
    } finally {
      setSavingAssignments(null);
    }
  }

  async function resend(haId: string) {
    setError(''); setNotice('');
    try {
      const updated = await apiFetch<HumanAgent>(`/owner/human-agents/${haId}/resend-invite`, { method: 'POST' });
      setHumanAgents((prev) => prev.map((h) => h.id === haId ? { ...h, ...updated } : h));
      setNotice(`Invite resent to ${updated.email}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Resend failed');
    }
  }

  async function remove(haId: string) {
    if (!confirm('Delete this human agent? They will lose access immediately.')) return;
    setError('');
    try {
      await apiFetch(`/owner/human-agents/${haId}`, { method: 'DELETE' });
      setHumanAgents((prev) => prev.filter((h) => h.id !== haId));
      setNotice('Human agent deleted');
      loadAnalytics();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  function toggleAssignment(haId: string, agentId: string) {
    setSelectedAssignments((prev) => {
      const cur = prev[haId] || [];
      const next = cur.includes(agentId) ? cur.filter((x) => x !== agentId) : [...cur, agentId];
      return { ...prev, [haId]: next };
    });
  }

  async function openConv(id: string) {
    setDetailLoading(true);
    try {
      const data = await apiFetch<ConvDetail>(`/owner/team/conversations/${id}`, { cacheMs: 0, dedupe: false });
      setSelectedConv(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load conversation');
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <AppLayout>
      <div className="max-w-[1100px] mx-auto space-y-8">
        <header className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Team</h1>
            <p className="text-sm text-on-surface-variant mt-2 max-w-2xl">
              Invite human agents, manage assignments, and review team performance. Human agents only see conversations for AI agents you assign them to.
            </p>
          </div>
          <button
            onClick={() => document.getElementById('invite-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            className="inline-flex items-center gap-2 h-10 px-5 rounded-xl bg-zinc-900 text-white text-sm font-bold hover:bg-zinc-800 shadow-sm shrink-0"
          >
            <UserPlus className="w-4 h-4" />
            Invite team
          </button>
        </header>

        {(error || notice) && (
          <div className={cn('rounded-xl border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>
            {error || notice}
          </div>
        )}

        {/* Analytics */}
        <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-widest uppercase text-on-surface-variant flex items-center gap-2"><BarChart3 className="w-4 h-4" /> Team overview</h2>
            <button onClick={() => loadAnalytics()} className="text-xs font-bold text-on-surface-variant hover:text-brand-primary">Refresh</button>
          </div>
          {aLoading ? (
            <div className="mt-6 flex items-center justify-center py-8 text-sm text-on-surface-variant"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading analytics…</div>
          ) : analytics ? (
            <div className="mt-6 space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl border border-surface-container-highest bg-surface p-4">
                  <div className="text-[11px] font-black uppercase tracking-widest text-on-surface-variant">Total cases</div>
                  <div className="text-2xl font-bold text-brand-primary mt-1">{analytics.total}</div>
                  <div className="text-xs text-on-surface-variant mt-1">All conversations</div>
                </div>
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="text-[11px] font-black uppercase tracking-widest text-emerald-700">Cases closed</div>
                  <div className="text-2xl font-bold text-emerald-700 mt-1">{analytics.cases_closed}</div>
                  <div className="text-xs text-emerald-700/70 mt-1">Resolved</div>
                </div>
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <div className="text-[11px] font-black uppercase tracking-widest text-amber-700">Queued</div>
                  <div className="text-2xl font-bold text-amber-700 mt-1">{analytics.queued}</div>
                  <div className="text-xs text-amber-700/70 mt-1">Waiting for human</div>
                </div>
                <div className="rounded-xl border border-sky-200 bg-sky-50 p-4">
                  <div className="text-[11px] font-black uppercase tracking-widest text-sky-700">Active</div>
                  <div className="text-2xl font-bold text-sky-700 mt-1">{analytics.human}</div>
                  <div className="text-xs text-sky-700/70 mt-1">With human</div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-xs font-black uppercase tracking-widest text-on-surface-variant mb-3">Per human agent</h3>
                  {analytics.by_human.length === 0 ? (
                    <div className="text-sm text-on-surface-variant">No human agents yet.</div>
                  ) : (
                    <div className="space-y-2">
                      {analytics.by_human.map((h) => (
                        <div key={h.id} className="flex items-center justify-between rounded-lg border border-surface-container-highest bg-surface px-3 py-2.5">
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-brand-primary truncate">{h.name || h.email.split('@')[0]} <span className="text-xs text-on-surface-variant">· {h.email}</span></div>
                            <div className="text-xs text-on-surface-variant">{h.total} total · <span className="text-amber-700">{h.queued} queued</span> · <span className="text-sky-700">{h.human} active</span> · <span className="text-emerald-700">{h.resolved} closed</span></div>
                          </div>
                          <span className={cn('text-[10px] font-black uppercase tracking-widest px-1.5 py-1 rounded border', h.status==='active'?'bg-emerald-50 border-emerald-200 text-emerald-700':'bg-amber-50 border-amber-200 text-amber-700')}>{h.status}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <h3 className="text-xs font-black uppercase tracking-widest text-on-surface-variant mb-3">Per AI agent</h3>
                  {analytics.by_agent.length === 0 ? (
                    <div className="text-sm text-on-surface-variant">No AI agents yet.</div>
                  ) : (
                    <div className="space-y-2">
                      {analytics.by_agent.map((a) => (
                        <div key={a.id} className="rounded-lg border border-surface-container-highest bg-surface px-3 py-2.5">
                          <div className="text-sm font-semibold text-brand-primary">{a.name}</div>
                          <div className="text-xs text-on-surface-variant mt-1 flex flex-wrap gap-2">
                            {Object.entries(a.by_status).map(([k,v]) => (
                              <span key={k} className="inline-flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-zinc-400" />{k}: {v}</span>
                            ))}
                            {a.total===0 && <span>no conversations</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-on-surface-variant mt-6">No data.</div>
          )}
        </section>

        {/* Conversations */}
        <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-container-highest flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-bold text-brand-primary flex items-center gap-2"><MessageSquare className="w-4 h-4" /> Conversations {cTotal? `(${cTotal})` : ''}</h2>
            <div className="flex items-center gap-2">
              <select value={filterStatus} onChange={(e)=>setFilterStatus(e.target.value)} className="h-8 rounded-lg border border-surface-container-highest bg-surface px-2 text-xs font-semibold">
                <option value="">All statuses</option>
                <option value="bot">bot</option>
                <option value="collecting_email">collecting_email</option>
                <option value="queued">queued</option>
                <option value="human">human</option>
                <option value="resolved">resolved</option>
              </select>
              <select value={filterAgent} onChange={(e)=>setFilterAgent(e.target.value)} className="h-8 rounded-lg border border-surface-container-highest bg-surface px-2 text-xs font-semibold">
                <option value="">All AI agents</option>
                {agents.map((a)=> <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <button onClick={loadConvs} className="h-8 px-3 rounded-lg border border-surface-container-highest bg-surface text-xs font-bold">Refresh</button>
            </div>
          </div>
          {cLoading ? (
            <div className="p-8 flex items-center justify-center text-sm text-on-surface-variant"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
          ) : convs.length===0 ? (
            <div className="p-8 text-center text-sm text-on-surface-variant">No conversations for this filter.</div>
          ) : (
            <div className="divide-y divide-surface-container-highest max-h-[420px] overflow-y-auto">
              {convs.map((c)=> (
                <button key={c.id} onClick={()=>openConv(c.id)} className="w-full text-left px-6 py-3 hover:bg-surface-container-low flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-brand-primary truncate">{c.visitor_email || c.visitor_id} <span className="text-xs text-on-surface-variant">· {c.preview?.slice(0,60) || 'no preview'}</span></div>
                    <div className="text-xs text-on-surface-variant">{c.status} · {c.assigned_human_name || 'unassigned'} · {c.updated_at ? new Date(c.updated_at).toLocaleString() : ''}</div>
                  </div>
                  <span className={cn('text-[10px] font-black uppercase tracking-widest px-1.5 py-1 rounded border shrink-0', c.status==='resolved'?'bg-emerald-50 border-emerald-200 text-emerald-700':c.status==='queued'?'bg-amber-50 border-amber-200 text-amber-700':c.status==='human'?'bg-sky-50 border-sky-200 text-sky-700':'bg-zinc-100 border-zinc-200 text-zinc-600')}>{c.status}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {selectedConv && (
          <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm p-4 md:p-8 flex items-center justify-center" onClick={()=>setSelectedConv(null)}>
            <div className="bg-white rounded-2xl border border-zinc-200 w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden" onClick={(e)=>e.stopPropagation()}>
              <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between">
                <div>
                  <div className="text-sm font-bold">{selectedConv.visitor_email || selectedConv.visitor_id} · {selectedConv.status}</div>
                  <div className="text-xs text-zinc-500">{selectedConv.id.slice(0,8)} · {selectedConv.assigned_human_name || 'unassigned'}</div>
                </div>
                <button onClick={()=>setSelectedConv(null)} className="h-8 w-8 grid place-items-center rounded-lg border border-zinc-200"><X className="w-4 h-4" /></button>
              </div>
              <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-[#fcfcfc]">
                {detailLoading ? <div className="flex items-center justify-center py-10"><Loader2 className="w-5 h-5 animate-spin" /></div> : selectedConv.messages.length===0 ? <div className="text-sm text-zinc-500">No messages.</div> : selectedConv.messages.map((m)=> (
                  <div key={m.id} className={m.sender_type==='visitor' ? 'flex justify-end' : 'flex justify-start'}>
                    <div className={m.sender_type==='visitor' ? 'bg-zinc-900 text-white rounded-2xl rounded-br-sm px-4 py-3 max-w-[80%] text-sm' : m.sender_type==='human_agent' ? 'bg-white border border-zinc-200 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%] text-sm shadow-sm' : 'bg-zinc-100 border border-zinc-200 rounded-2xl px-4 py-3 max-w-[80%] text-sm'}>
                      <div className="text-[10px] font-bold uppercase tracking-widest opacity-60 mb-1">{m.sender_type}</div>
                      <div className="whitespace-pre-wrap break-words">{m.content}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-4 border-t border-zinc-200 flex justify-end">
                <button onClick={()=>setSelectedConv(null)} className="h-9 px-4 rounded-xl bg-zinc-900 text-white text-sm font-bold">Close</button>
              </div>
            </div>
          </div>
        )}

        {/* Invite */}
        <section id="invite-section" className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6 scroll-mt-6">
          <h2 className="text-sm font-bold tracking-widest uppercase text-on-surface-variant flex items-center gap-2"><UserPlus className="w-4 h-4" /> Invite human agent</h2>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-3">
            <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="agent@yourcompany.com" className="h-11 rounded-lg border border-surface-container-highest bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none" />
            <input value={inviteName} onChange={(e) => setInviteName(e.target.value)} placeholder="Name (optional)" className="h-11 rounded-lg border border-surface-container-highest bg-surface px-4 text-sm focus:border-brand-primary focus:outline-none" />
            <button onClick={invite} disabled={inviting || !inviteEmail.trim()} className="h-11 px-6 rounded-lg bg-brand-primary text-brand-on-primary text-sm font-bold hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2">
              {inviting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}Invite
            </button>
          </div>
          <p className="text-xs text-on-surface-variant mt-3">They'll receive an email via frelo.com.ng with a 7-day setup link. Until you assign them to an AI agent, they see an empty dashboard.</p>
        </section>

        {/* List */}
        <section className="rounded-xl border border-surface-container-highest bg-surface-container-lowest overflow-hidden">
          <div className="px-6 py-4 border-b border-surface-container-highest flex items-center justify-between">
            <h2 className="text-sm font-bold text-brand-primary flex items-center gap-2"><Shield className="w-4 h-4" /> Human agents ({humanAgents.length})</h2>
            <button onClick={load} className="text-xs font-bold text-on-surface-variant hover:text-brand-primary">Refresh</button>
          </div>

          {loading ? (
            <div className="p-10 flex items-center justify-center text-sm text-on-surface-variant"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…</div>
          ) : humanAgents.length === 0 ? (
            <div className="p-10 text-center">
              <div className="mx-auto w-12 h-12 rounded-xl bg-surface-container-low grid place-items-center text-on-surface-variant"><Mail className="w-6 h-6" /></div>
              <p className="mt-3 font-semibold text-brand-primary">No human agents yet</p>
              <p className="text-sm text-on-surface-variant mt-1">Invite someone to get started.</p>
            </div>
          ) : (
            <div className="divide-y divide-surface-container-highest">
              {humanAgents.map((ha) => {
                const dirty = JSON.stringify((selectedAssignments[ha.id] || []).sort()) !== JSON.stringify((ha.assignments || []).sort());
                return (
                  <div key={ha.id} className="p-6 space-y-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-brand-primary text-brand-on-primary grid place-items-center text-sm font-bold">{(ha.name || ha.email).slice(0,2).toUpperCase()}</div>
                          <div>
                            <div className="font-semibold text-brand-primary">{ha.name || ha.email.split('@')[0]}</div>
                            <div className="text-xs text-on-surface-variant">{ha.email}</div>
                          </div>
                          <span className={cn('text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded-full border',
                            ha.status === 'active' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                            ha.status === 'invited' ? 'bg-amber-50 border-amber-200 text-amber-700' :
                            'bg-zinc-100 border-zinc-200 text-zinc-600'
                          )}>{ha.status}</span>
                        </div>
                        {ha.invite_link && (
                          <div className="mt-3 flex items-center gap-2 text-xs bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                            <span className="truncate flex-1 text-amber-800">Invite link (dev): {ha.invite_link}</span>
                            <button onClick={() => navigator.clipboard.writeText(ha.invite_link!)} className="p-1 hover:bg-amber-100 rounded"><Copy className="w-3.5 h-3.5" /></button>
                            <a href={ha.invite_link} target="_blank" rel="noreferrer" className="p-1 hover:bg-amber-100 rounded"><ExternalLink className="w-3.5 h-3.5" /></a>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {ha.status === 'invited' && <button onClick={() => resend(ha.id)} className="h-8 px-3 rounded-lg border border-surface-container-highest bg-surface text-xs font-bold hover:bg-surface-container-low flex items-center gap-1"><Send className="w-3 h-3" /> Resend</button>}
                        <button onClick={() => remove(ha.id)} className="h-8 w-8 grid place-items-center rounded-lg border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"><Trash2 className="w-4 h-4" /></button>
                      </div>
                    </div>

                    <div>
                      <div className="text-[11px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Assigned AI agents</div>
                      {agents.length === 0 ? (
                        <div className="text-sm text-on-surface-variant">No AI agents yet — create one on the Agents page first.</div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {agents.map((ag) => {
                            const checked = (selectedAssignments[ha.id] || []).includes(ag.id);
                            return (
                              <label key={ag.id} className={cn('flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer', checked ? 'border-brand-primary bg-surface' : 'border-surface-container-highest bg-surface hover:bg-surface-container-low')}>
                                <input type="checkbox" checked={checked} onChange={() => toggleAssignment(ha.id, ag.id)} className="h-4 w-4 accent-brand-primary" />
                                <div className="min-w-0 flex-1">
                                  <div className="text-sm font-semibold truncate text-brand-primary">{ag.name}</div>
                                  <div className="text-[11px] text-on-surface-variant">{ag.model}</div>
                                </div>
                                {checked && <Check className="w-4 h-4 text-brand-primary" />}
                              </label>
                            );
                          })}
                        </div>
                      )}
                      {dirty && (
                        <div className="mt-3 flex gap-2">
                          <button onClick={() => saveAssignments(ha.id)} disabled={savingAssignments === ha.id} className="h-9 px-4 rounded-lg bg-brand-primary text-brand-on-primary text-xs font-bold disabled:opacity-50 flex items-center gap-2">
                            {savingAssignments === ha.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />} Save assignments
                          </button>
                          <button onClick={() => setSelectedAssignments((p) => ({ ...p, [ha.id]: ha.assignments || [] }))} className="h-9 px-4 rounded-lg border border-surface-container-highest bg-surface text-xs font-bold flex items-center gap-2"><X className="w-3 h-3" /> Reset</button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </AppLayout>
  );
}
