import {
  Database,
  FileText,
  Link as LinkIcon,
  Loader2,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
  Upload,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { Agent, apiFetch, formatRelative, KnowledgeBase } from '../lib/api';

type SourceRow = KnowledgeBase & { agentName: string };

function sourceLabel(t: KnowledgeBase['source_type']) {
  const labels: Record<KnowledgeBase['source_type'], string> = {
    upload_pdf: 'PDF',
    upload_txt: 'Text file',
    url: 'Website',
    text: 'Text',
    other: 'File',
  };
  return labels[t] ?? 'Source';
}

function normalizeUrl(input: string): string {
  const t = input.trim();
  if (!t) return '';
  if (/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(t)) return t;
  return `https://${t}`;
}

export default function Knowledge() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [rows, setRows] = useState<SourceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  // add-source form
  const [agentId, setAgentId] = useState('');
  const [mode, setMode] = useState<'url' | 'file' | 'text'>('url');
  const [title, setTitle] = useState('');
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [adding, setAdding] = useState(false);

  const filterAgent = searchParams.get('agent') ?? '';

  async function load() {
    setLoading(true);
    setError('');
    try {
      const ag = await apiFetch<Agent[]>('/agents/');
      setAgents(ag);
      if (ag.length === 0) {
        setRows([]);
        return;
      }
      const all = await Promise.all(
        ag.map(async (a) => {
          try {
            const kbs = await apiFetch<KnowledgeBase[]>(`/kb/${a.id}`);
            return kbs.map((kb) => ({ ...kb, agentName: a.name }));
          } catch {
            return [] as SourceRow[];
          }
        })
      );
      setRows(all.flat());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load knowledge base');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(
    () => (filterAgent ? rows.filter((r) => r.agent_id === filterAgent) : rows),
    [rows, filterAgent]
  );

  const readyCount = filtered.filter((r) => r.status === 'ready').length;

  function selectAgent(id: string) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (id) next.set('agent', id);
      else next.delete('agent');
      return next;
    });
  }

  async function addSource() {
    if (!agentId) {
      setError('Choose an agent first.');
      return;
    }
    setAdding(true);
    setError('');
    setNotice('');
    try {
      const body = new FormData();
      body.append('agent_id', agentId);
      if (title.trim()) body.append('title', title.trim());
      if (mode === 'url') {
        if (!url.trim()) throw new Error('Enter a website URL.');
        body.append('source_type', 'url');
        body.append('url', normalizeUrl(url.trim()));
      } else if (mode === 'text') {
        if (!text.trim()) throw new Error('Enter some knowledge text.');
        body.append('source_type', 'text');
        body.append('structured_text', text.trim());
      } else {
        if (!file) throw new Error('Choose a file to upload.');
        const lower = file.name.toLowerCase();
        body.append('source_type', lower.endsWith('.pdf') ? 'upload_pdf' : lower.endsWith('.txt') ? 'upload_txt' : 'other');
        body.append('file', file);
      }
      await apiFetch<KnowledgeBase>('/kb/add', { method: 'POST', body });
      setTitle('');
      setUrl('');
      setText('');
      setFile(null);
      setNotice('Knowledge source added. Indexing has started.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add source');
    } finally {
      setAdding(false);
    }
  }

  async function remove(kb: SourceRow) {
    if (!confirm(`Delete "${kb.title || kb.source_uri || 'this source'}"?`)) return;
    setError('');
    try {
      await apiFetch(`/kb/${kb.id}`, { method: 'DELETE' });
      setNotice('Source deleted.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete source');
    }
  }

  async function reindex(kb: SourceRow) {
    setError('');
    setNotice('');
    try {
      await apiFetch(`/kb/${kb.id}/reindex`, { method: 'POST' });
      setNotice('Retraining started for this source.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retrain source');
    }
  }

  async function retrainAll() {
    if (!filterAgent) return;
    setError('');
    setNotice('');
    try {
      await apiFetch(`/kb/agent/${filterAgent}/retrain`, { method: 'POST' });
      setNotice('Retraining started for all sources on this agent.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not retrain');
    }
  }

  return (
    <AppLayout>
      <div className="space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Knowledge</h1>
            <p className="mt-1 text-sm text-on-surface-variant">
              Everything your agents are trained on — add sources, retrain, and keep answers accurate.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={filterAgent}
              onChange={(e) => selectAgent(e.target.value)}
              className="h-10 rounded-lg border border-surface-container-highest bg-white px-3 text-sm font-medium focus:border-brand-primary focus:outline-none"
            >
              <option value="">All agents</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
            {filterAgent && (
              <button
                onClick={retrainAll}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-surface-container-highest bg-white px-3 text-sm font-semibold text-brand-primary hover:bg-zinc-50"
              >
                <RotateCcw className="h-4 w-4" /> Retrain all
              </button>
            )}
          </div>
        </header>

        {(error || notice) && (
          <div className={cn('rounded-lg border px-4 py-3 text-sm font-medium', error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700')}>
            {error || notice}
          </div>
        )}

        {agents.length === 0 && !loading ? (
          <div className="rounded-xl border border-dashed border-surface-container-highest bg-white p-10 text-center">
            <Database className="mx-auto mb-3 h-10 w-10 text-zinc-300" strokeWidth={1.5} />
            <p className="font-semibold text-brand-primary">No agents yet</p>
            <p className="mt-1 text-sm text-on-surface-variant">Create an agent first, then add knowledge here.</p>
            <Link to="/agents" className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 text-sm font-semibold text-brand-on-primary hover:opacity-90">
              <Plus className="h-4 w-4" /> Create agent
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
            {/* Add source */}
            <aside className="h-fit rounded-xl border border-surface-container-highest bg-white p-5">
              <h2 className="flex items-center gap-2 text-sm font-bold text-brand-primary">
                <Plus className="h-4 w-4" /> Add a source
              </h2>
              <p className="mt-1 text-xs text-on-surface-variant">Pick an agent and a source type, then add it.</p>

              <div className="mt-4 space-y-4">
                <label className="block space-y-1.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant">Agent</span>
                  <select
                    value={agentId}
                    onChange={(e) => setAgentId(e.target.value)}
                    className="h-10 w-full rounded-lg border border-surface-container-highest bg-white px-3 text-sm focus:border-brand-primary focus:outline-none"
                  >
                    <option value="">Choose an agent…</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name}</option>
                    ))}
                  </select>
                </label>

                <div className="flex rounded-lg border border-surface-container-highest bg-zinc-50 p-1">
                  {([['url', 'URL', LinkIcon], ['file', 'File', Upload], ['text', 'Text', FileText]] as const).map(([value, label, Icon]) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setMode(value)}
                      className={cn(
                        'flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-2 text-xs font-semibold transition-colors',
                        mode === value ? 'bg-brand-primary text-white' : 'text-on-surface-variant hover:text-brand-primary'
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" /> {label}
                    </button>
                  ))}
                </div>

                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Title (optional)"
                  className="h-10 w-full rounded-lg border border-surface-container-highest bg-white px-3 text-sm focus:border-brand-primary focus:outline-none"
                />

                {mode === 'url' && (
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="example.com/help"
                    className="h-10 w-full rounded-lg border border-surface-container-highest bg-white px-3 text-sm focus:border-brand-primary focus:outline-none"
                  />
                )}
                {mode === 'text' && (
                  <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Paste policies, FAQs, or product docs…"
                    rows={5}
                    className="w-full resize-none rounded-lg border border-surface-container-highest bg-white p-3 text-sm focus:border-brand-primary focus:outline-none"
                  />
                )}
                {mode === 'file' && (
                  <label className="flex min-h-24 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-surface-container-highest bg-zinc-50 text-center hover:border-brand-primary">
                    <Upload className="mb-2 h-5 w-5 text-on-surface-variant" />
                    <span className="text-sm font-semibold text-brand-primary">{file?.name || 'Choose a file'}</span>
                    <span className="text-xs text-on-surface-variant">PDF, TXT, DOCX</span>
                    <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  </label>
                )}

                <button
                  onClick={addSource}
                  disabled={adding || !agentId}
                  className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-primary text-sm font-semibold text-brand-on-primary hover:opacity-90 disabled:opacity-50"
                >
                  {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Add source
                </button>
              </div>
            </aside>

            {/* Source list */}
            <section className="overflow-hidden rounded-xl border border-surface-container-highest bg-white">
              <div className="flex items-center justify-between border-b border-surface-container-highest px-5 py-3.5">
                <h2 className="text-sm font-bold text-brand-primary">
                  Sources ({filtered.length}) <span className="font-normal text-on-surface-variant">· {readyCount} ready</span>
                </h2>
                <button onClick={load} className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant hover:text-brand-primary">
                  <RefreshCw className="h-3.5 w-3.5" /> Refresh
                </button>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-16 text-sm text-on-surface-variant">
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading sources…
                </div>
              ) : filtered.length === 0 ? (
                <div className="px-6 py-14 text-center text-sm text-on-surface-variant">
                  <Database className="mx-auto mb-2 h-8 w-8 text-zinc-300" /> No knowledge sources yet.
                </div>
              ) : (
                <div className="divide-y divide-surface-container-highest">
                  {filtered.map((kb) => (
                    <div key={kb.id} className="flex items-center justify-between gap-4 px-5 py-4">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-zinc-100 text-on-surface-variant">
                          {kb.source_type === 'url' ? <LinkIcon className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-brand-primary">{kb.title || kb.source_uri || 'Untitled source'}</p>
                          <p className="text-xs text-on-surface-variant">
                            {sourceLabel(kb.source_type)} · {kb.agentName} · Added {formatRelative(kb.created_at)}
                          </p>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide',
                            kb.status === 'ready' && 'bg-emerald-100 text-emerald-700',
                            kb.status === 'pending' && 'bg-amber-100 text-amber-700',
                            kb.status === 'failed' && 'bg-rose-100 text-rose-700'
                          )}
                        >
                          {kb.status}
                        </span>
                        <button onClick={() => reindex(kb)} title="Retrain" className="grid h-8 w-8 place-items-center rounded-lg border border-surface-container-highest text-on-surface-variant hover:bg-zinc-50 hover:text-brand-primary">
                          <RotateCcw className="h-4 w-4" />
                        </button>
                        <button onClick={() => remove(kb)} title="Delete" className="grid h-8 w-8 place-items-center rounded-lg border border-surface-container-highest text-on-surface-variant hover:bg-rose-50 hover:text-rose-600">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
