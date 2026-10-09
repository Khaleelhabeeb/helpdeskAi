import { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, Loader2, Pencil, Play, Plus, Trash2, X, Zap } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
type ParamType = 'string' | 'number' | 'boolean';

type ActionParam = { name: string; type: ParamType; description: string; required: boolean };
type ActionHeader = { name: string; value: string };

export type AgentAction = {
  id: string;
  name: string;
  description: string;
  method: HttpMethod;
  url: string;
  parameters: ActionParam[];
  headers: ActionHeader[];
  enabled: boolean;
  timeout_seconds: number;
};

type Draft = Omit<AgentAction, 'id'> & { id?: string };

type TestResult = { ok: boolean; status: number | null; error: string | null; duration_ms: number; body: string };

const METHODS: HttpMethod[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];
const NAME_RE = /^[a-z][a-z0-9_]{2,47}$/;

const EMPTY_DRAFT: Draft = {
  name: '',
  description: '',
  method: 'GET',
  url: 'https://',
  parameters: [],
  headers: [],
  enabled: true,
  timeout_seconds: 10,
};

const ORDER_TEMPLATE: Draft = {
  name: 'get_order_status',
  description: 'Look up the shipping status of a customer order. Use when the customer asks where their order is or when it will arrive.',
  method: 'GET',
  url: 'https://api.yourstore.com/orders/{order_id}',
  parameters: [{ name: 'order_id', type: 'string', description: 'The order number, e.g. A10023', required: true }],
  headers: [{ name: 'Authorization', value: 'Bearer ' }],
  enabled: true,
  timeout_seconds: 10,
};

function placeholders(url: string) {
  return Array.from(url.matchAll(/\{([^{}]+)\}/g)).map((m) => m[1]);
}

const methodTone: Record<HttpMethod, string> = {
  GET: 'bg-sky-50 text-sky-700 ring-sky-200',
  POST: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  PUT: 'bg-amber-50 text-amber-700 ring-amber-200',
  PATCH: 'bg-amber-50 text-amber-700 ring-amber-200',
  DELETE: 'bg-rose-50 text-rose-700 ring-rose-200',
};

function MethodBadge({ method }: { method: HttpMethod }) {
  return <span className={cn('rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ring-1', methodTone[method])}>{method}</span>;
}

const inputCls =
  'w-full rounded-lg border border-hairline bg-white px-3 py-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:ring-2 focus:ring-zinc-900/10';

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-sm font-medium text-zinc-900">{label}</p>
      {hint && <p className="mb-2 mt-0.5 text-xs text-zinc-500">{hint}</p>}
      <div className={hint ? '' : 'mt-1.5'}>{children}</div>
    </div>
  );
}

export function AgentActions({ agentId }: { agentId: string }) {
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setActions(await apiFetch<AgentAction[]>(`/agents/${agentId}/actions`));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load actions');
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load]);

  async function toggle(action: AgentAction) {
    setActions((cur) => cur.map((a) => (a.id === action.id ? { ...a, enabled: !a.enabled } : a)));
    try {
      await apiFetch(`/agents/${agentId}/actions/${action.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !action.enabled }),
      });
    } catch (err) {
      setActions((cur) => cur.map((a) => (a.id === action.id ? action : a)));
      setError(err instanceof Error ? err.message : 'Could not update action');
    }
  }

  async function remove(action: AgentAction) {
    if (!window.confirm(`Delete the "${action.name}" action? The agent will stop using it immediately.`)) return;
    try {
      await apiFetch(`/agents/${agentId}/actions/${action.id}`, { method: 'DELETE' });
      setActions((cur) => cur.filter((a) => a.id !== action.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete action');
    }
  }

  if (draft) {
    return (
      <ActionEditor
        agentId={agentId}
        initial={draft}
        onCancel={() => setDraft(null)}
        onSaved={(saved) => {
          setActions((cur) => (cur.some((a) => a.id === saved.id) ? cur.map((a) => (a.id === saved.id ? saved : a)) : [...cur, saved]));
          setDraft({ ...saved });
        }}
      />
    );
  }

  return (
    <section className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-950">Actions</h2>
          <p className="mt-1 text-sm text-zinc-500">
            Let your agent call your APIs mid-conversation — look up orders, check accounts, create tickets.
          </p>
        </div>
        <button
          onClick={() => setDraft({ ...EMPTY_DRAFT })}
          className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
        >
          <Plus className="h-4 w-4" /> New action
        </button>
      </div>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {loading ? (
        <div className="grid place-items-center rounded-2xl border border-hairline bg-white py-16">
          <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
        </div>
      ) : actions.length === 0 ? (
        <div className="rounded-2xl border border-hairline bg-white px-6 py-14 text-center">
          <div className="mx-auto grid h-11 w-11 place-items-center rounded-xl border border-hairline bg-white shadow-soft">
            <Zap className="h-5 w-5 text-zinc-900" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-zinc-950">No actions yet</h3>
          <p className="mx-auto mt-1 max-w-sm text-sm text-zinc-500">
            Connect an API endpoint and describe when to use it. The agent decides when to call it and fills in the details from the chat.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <button onClick={() => setDraft({ ...EMPTY_DRAFT })} className="inline-flex h-9 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white hover:bg-zinc-800">
              <Plus className="h-4 w-4" /> Custom API action
            </button>
            <button onClick={() => setDraft({ ...ORDER_TEMPLATE, parameters: [...ORDER_TEMPLATE.parameters], headers: [...ORDER_TEMPLATE.headers] })} className="inline-flex h-9 items-center rounded-lg border border-hairline bg-white px-4 text-sm font-medium text-zinc-900 hover:bg-zinc-50">
              Start from “order lookup” example
            </button>
          </div>
        </div>
      ) : (
        <div className="divide-y divide-hairline overflow-hidden rounded-2xl border border-hairline bg-white">
          {actions.map((action) => (
            <div key={action.id} className="flex items-center gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-sm font-medium text-zinc-950">{action.name}</span>
                  <MethodBadge method={action.method} />
                  {!action.enabled && <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500">Off</span>}
                </div>
                <p className="mt-1 truncate text-sm text-zinc-500">{action.description}</p>
              </div>
              <button
                role="switch"
                aria-checked={action.enabled}
                aria-label={action.enabled ? 'Turn off' : 'Turn on'}
                onClick={() => toggle(action)}
                className={cn('relative h-5 w-9 shrink-0 rounded-full transition-colors', action.enabled ? 'bg-zinc-950' : 'bg-zinc-200')}
              >
                <span className={cn('absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all', action.enabled ? 'left-[18px]' : 'left-0.5')} />
              </button>
              <button onClick={() => setDraft({ ...action })} className="grid h-8 w-8 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900" aria-label="Edit">
                <Pencil className="h-4 w-4" />
              </button>
              <button onClick={() => remove(action)} className="grid h-8 w-8 place-items-center rounded-lg text-zinc-500 hover:bg-rose-50 hover:text-rose-600" aria-label="Delete">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ActionEditor({
  agentId,
  initial,
  onCancel,
  onSaved,
}: {
  agentId: string;
  initial: Draft;
  onCancel: () => void;
  onSaved: (action: AgentAction) => void;
}) {
  const [draft, setDraft] = useState<Draft>(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [savedSnapshot, setSavedSnapshot] = useState(initial.id ? JSON.stringify(initial) : '');
  const [testArgs, setTestArgs] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const isSaved = !!draft.id;
  const isDirty = JSON.stringify(draft) !== savedSnapshot;
  const urlParams = useMemo(() => placeholders(draft.url), [draft.url]);
  const undefinedParams = urlParams.filter((p) => !draft.parameters.some((x) => x.name === p));
  const nameError = draft.name && !NAME_RE.test(draft.name) ? 'Use lowercase letters, numbers and underscores (3–48), starting with a letter.' : '';

  function patch(next: Partial<Draft>) {
    setDraft((cur) => ({ ...cur, ...next }));
  }

  // Typing {placeholder} in the URL adds a matching parameter so the two never drift apart
  function onUrlChange(url: string) {
    const names = placeholders(url);
    setDraft((cur) => {
      const missing = names.filter((n) => /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(n) && !cur.parameters.some((p) => p.name === n));
      return {
        ...cur,
        url,
        parameters: [...cur.parameters, ...missing.map((name) => ({ name, type: 'string' as ParamType, description: '', required: true }))],
      };
    });
  }

  async function save() {
    setSaving(true);
    setError('');
    try {
      const body = JSON.stringify({
        name: draft.name,
        description: draft.description,
        method: draft.method,
        url: draft.url,
        parameters: draft.parameters,
        headers: draft.headers.filter((h) => h.name.trim()),
        enabled: draft.enabled,
        timeout_seconds: draft.timeout_seconds,
      });
      const saved = await apiFetch<AgentAction>(
        draft.id ? `/agents/${agentId}/actions/${draft.id}` : `/agents/${agentId}/actions`,
        { method: draft.id ? 'PUT' : 'POST', body }
      );
      setDraft(saved);
      setSavedSnapshot(JSON.stringify(saved));
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save action');
    } finally {
      setSaving(false);
    }
  }

  async function runTest() {
    if (!draft.id) return;
    setTesting(true);
    setTestResult(null);
    try {
      const args: Record<string, unknown> = {};
      for (const p of draft.parameters) {
        const raw = testArgs[p.name];
        if (raw === undefined || raw === '') continue;
        args[p.name] = p.type === 'number' ? Number(raw) : p.type === 'boolean' ? raw === 'true' : raw;
      }
      setTestResult(
        await apiFetch<TestResult>(`/agents/${agentId}/actions/${draft.id}/test`, {
          method: 'POST',
          body: JSON.stringify({ arguments: args }),
        })
      );
    } catch (err) {
      setTestResult({ ok: false, status: null, error: err instanceof Error ? err.message : 'Test failed', duration_ms: 0, body: '' });
    } finally {
      setTesting(false);
    }
  }

  const prettyBody = useMemo(() => {
    if (!testResult?.body) return '';
    try {
      return JSON.stringify(JSON.parse(testResult.body), null, 2);
    } catch {
      return testResult.body;
    }
  }, [testResult]);

  const canSave = !!draft.name && !nameError && draft.description.trim().length >= 10 && draft.url.length > 8 && undefinedParams.length === 0;

  return (
    <section className="mx-auto max-w-5xl">
      <button onClick={onCancel} className="mb-4 inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-950">
        <ChevronLeft className="h-4 w-4" /> All actions
      </button>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-6 rounded-2xl border border-hairline bg-white p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold tracking-tight text-zinc-950">{isSaved ? 'Edit action' : 'New custom API action'}</h2>
            {isSaved && !isDirty && <span className="text-xs text-emerald-600">Saved</span>}
          </div>

          {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}

          <Field label="Name" hint="How the agent refers to this action internally.">
            <input value={draft.name} onChange={(e) => patch({ name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })} placeholder="get_order_status" className={cn(inputCls, 'font-mono')} />
            {nameError && <p className="mt-1.5 text-xs text-rose-600">{nameError}</p>}
          </Field>

          <Field label="When should the agent use this?" hint="Be specific — this is what the agent reads to decide. Include what it returns.">
            <textarea value={draft.description} onChange={(e) => patch({ description: e.target.value })} rows={3} maxLength={1000} placeholder="Look up the shipping status of an order. Use when the customer asks where their order is." className={cn(inputCls, 'resize-none')} />
          </Field>

          <Field label="API endpoint" hint="Use {name} in the path or query to fill values from the conversation.">
            <div className="flex gap-2">
              <select value={draft.method} onChange={(e) => patch({ method: e.target.value as HttpMethod })} className={cn(inputCls, 'w-28 shrink-0 font-mono')}>
                {METHODS.map((m) => <option key={m}>{m}</option>)}
              </select>
              <input value={draft.url} onChange={(e) => onUrlChange(e.target.value)} placeholder="https://api.example.com/orders/{order_id}" className={cn(inputCls, 'font-mono')} />
            </div>
            {undefinedParams.length > 0 && <p className="mt-1.5 text-xs text-rose-600">Add parameters for: {undefinedParams.join(', ')}</p>}
          </Field>

          <Field
            label="Parameters"
            hint={draft.method === 'GET' || draft.method === 'DELETE' ? 'Values the agent collects. Ones not in the URL are sent as query parameters.' : 'Values the agent collects. Ones not in the URL are sent as a JSON body.'}
          >
            <div className="space-y-2">
              {draft.parameters.map((p, i) => (
                <div key={i} className="grid grid-cols-[1fr_96px_auto_auto] items-center gap-2 rounded-lg border border-hairline p-2 sm:grid-cols-[140px_96px_1fr_auto_auto]">
                  <input value={p.name} onChange={(e) => patch({ parameters: draft.parameters.map((x, j) => (j === i ? { ...x, name: e.target.value.replace(/[^a-zA-Z0-9_]/g, '') } : x)) })} placeholder="name" className={cn(inputCls, 'font-mono')} />
                  <select value={p.type} onChange={(e) => patch({ parameters: draft.parameters.map((x, j) => (j === i ? { ...x, type: e.target.value as ParamType } : x)) })} className={inputCls}>
                    <option value="string">text</option>
                    <option value="number">number</option>
                    <option value="boolean">yes/no</option>
                  </select>
                  <input value={p.description} onChange={(e) => patch({ parameters: draft.parameters.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)) })} placeholder="What is it? e.g. order number like A10023" className={cn(inputCls, 'col-span-4 sm:col-span-1')} />
                  <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-zinc-600">
                    <input type="checkbox" checked={p.required} onChange={(e) => patch({ parameters: draft.parameters.map((x, j) => (j === i ? { ...x, required: e.target.checked } : x)) })} className="h-3.5 w-3.5 accent-zinc-900" />
                    Required
                  </label>
                  <button onClick={() => patch({ parameters: draft.parameters.filter((_, j) => j !== i) })} className="grid h-8 w-8 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900" aria-label="Remove parameter">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <button onClick={() => patch({ parameters: [...draft.parameters, { name: '', type: 'string', description: '', required: true }] })} className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-950">
                <Plus className="h-4 w-4" /> Add parameter
              </button>
            </div>
          </Field>

          <Field label="Headers" hint="For API keys or auth tokens. Values are encrypted and never shown again.">
            <div className="space-y-2">
              {draft.headers.map((h, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input value={h.name} onChange={(e) => patch({ headers: draft.headers.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} placeholder="Authorization" className={cn(inputCls, 'w-44 shrink-0 font-mono')} />
                  <input type="password" autoComplete="off" value={h.value} onChange={(e) => patch({ headers: draft.headers.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)) })} placeholder="Bearer …" className={cn(inputCls, 'font-mono')} />
                  <button onClick={() => patch({ headers: draft.headers.filter((_, j) => j !== i) })} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900" aria-label="Remove header">
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <button onClick={() => patch({ headers: [...draft.headers, { name: '', value: '' }] })} className="inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-950">
                <Plus className="h-4 w-4" /> Add header
              </button>
            </div>
          </Field>

          <div className="flex items-center justify-between gap-3 border-t border-hairline pt-5">
            <label className="flex items-center gap-2 text-sm text-zinc-700">
              Timeout
              <select value={draft.timeout_seconds} onChange={(e) => patch({ timeout_seconds: Number(e.target.value) })} className={cn(inputCls, 'w-20 py-1.5')}>
                {[5, 10, 15, 20, 30].map((t) => <option key={t} value={t}>{t}s</option>)}
              </select>
            </label>
            <div className="flex gap-2">
              <button onClick={onCancel} className="h-9 rounded-lg border border-hairline px-4 text-sm font-medium text-zinc-900 hover:bg-zinc-50">Close</button>
              <button onClick={save} disabled={!canSave || saving || (isSaved && !isDirty)} className="inline-flex h-9 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40">
                {saving && <Loader2 className="h-4 w-4 animate-spin" />} {isSaved ? 'Save changes' : 'Create action'}
              </button>
            </div>
          </div>
        </div>

        {/* Test panel */}
        <div className="h-fit space-y-4 rounded-2xl border border-hairline bg-white p-6 lg:sticky lg:top-24">
          <div>
            <h3 className="text-sm font-semibold text-zinc-950">Test the call</h3>
            <p className="mt-1 text-xs text-zinc-500">
              {isSaved ? 'Runs the saved action with these values — exactly what the agent would send.' : 'Create the action first, then test it here.'}
            </p>
          </div>
          {isSaved && (
            <>
              {draft.parameters.length > 0 ? (
                <div className="space-y-2">
                  {draft.parameters.map((p) => (
                    <label key={p.name} className="block">
                      <span className="font-mono text-xs text-zinc-600">{p.name}{p.required && <span className="text-rose-500"> *</span>}</span>
                      <input value={testArgs[p.name] ?? ''} onChange={(e) => setTestArgs((cur) => ({ ...cur, [p.name]: e.target.value }))} placeholder={p.type === 'boolean' ? 'true / false' : p.description || p.type} className={cn(inputCls, 'mt-1')} />
                    </label>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500">This action has no parameters.</p>
              )}
              {isDirty && <p className="text-xs text-amber-600">You have unsaved changes — the test uses the saved version.</p>}
              <button onClick={runTest} disabled={testing} className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-hairline bg-white text-sm font-medium text-zinc-900 hover:bg-zinc-50 disabled:opacity-50">
                {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />} Run test
              </button>
              {testResult && (
                <div className="overflow-hidden rounded-lg border border-hairline">
                  <div className={cn('flex items-center justify-between px-3 py-2 text-xs font-medium', testResult.ok ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-800')}>
                    <span>{testResult.error ?? (testResult.ok ? 'Success' : 'Request failed')}{testResult.status ? ` · ${testResult.status}` : ''}</span>
                    {testResult.duration_ms > 0 && <span className="font-normal opacity-70">{testResult.duration_ms} ms</span>}
                  </div>
                  {prettyBody && <pre className="max-h-72 overflow-auto bg-zinc-50 p-3 font-mono text-[11px] leading-relaxed text-zinc-700">{prettyBody}</pre>}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
