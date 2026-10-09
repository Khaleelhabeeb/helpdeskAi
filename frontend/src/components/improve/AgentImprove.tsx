import { useCallback, useEffect, useState } from 'react';
import { Check, Loader2, MessageCircleQuestion, Pencil, Trash2 } from 'lucide-react';
import { apiFetch, formatRelative } from '../../lib/api';
import { cn } from '../../lib/utils';
import { Correction, CorrectionDialog } from './CorrectionDialog';

type UnansweredQuestion = {
  key: string;
  question: string;
  sample_answer: string;
  count: number;
  last_asked_at: string | null;
  message_ids: number[];
};

type Report = {
  days: number;
  total_replies: number;
  unanswered: number;
  rate: number;
  questions: UnansweredQuestion[];
};

type DialogState =
  | { mode: 'new'; question: string; originalAnswer?: string; messageIds: number[] }
  | { mode: 'edit'; correction: Correction };

const RANGES = [7, 30, 90];

function kbBadge(status: Correction['kb_status']) {
  if (status === 'ready') return <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">Live</span>;
  if (status === 'failed') return <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-700">Failed</span>;
  if (status === 'pending') return <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">Indexing</span>;
  return <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500">Source removed</span>;
}

export function AgentImprove({ agentId }: { agentId: string }) {
  const [days, setDays] = useState(30);
  const [report, setReport] = useState<Report | null>(null);
  const [corrections, setCorrections] = useState<Correction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialog, setDialog] = useState<DialogState | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [r, c] = await Promise.all([
        apiFetch<Report>(`/agents/${agentId}/unanswered?days=${days}`, { cacheMs: 0, dedupe: false }),
        apiFetch<Correction[]>(`/agents/${agentId}/corrections`, { cacheMs: 0, dedupe: false }),
      ]);
      setReport(r);
      setCorrections(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the report');
    } finally {
      setLoading(false);
    }
  }, [agentId, days]);

  useEffect(() => {
    load();
  }, [load]);

  async function dismiss(q: UnansweredQuestion) {
    setReport((cur) => cur && { ...cur, unanswered: cur.unanswered - q.count, questions: cur.questions.filter((x) => x.key !== q.key) });
    try {
      await apiFetch(`/agents/${agentId}/unanswered/dismiss`, { method: 'POST', body: JSON.stringify({ message_ids: q.message_ids }) });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not dismiss');
      load();
    }
  }

  async function removeCorrection(c: Correction) {
    if (!window.confirm('Delete this answer? The agent will stop using it.')) return;
    setCorrections((cur) => cur.filter((x) => x.id !== c.id));
    try {
      await apiFetch(`/agents/${agentId}/corrections/${c.id}`, { method: 'DELETE' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete');
      load();
    }
  }

  const pct = report && report.total_replies ? Math.round(report.rate * 100) : 0;

  return (
    <section className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-zinc-950">Improve answers</h2>
          <p className="mt-1 text-sm text-zinc-500">Questions your agent couldn't answer, and the answers you've taught it.</p>
        </div>
        <div className="flex rounded-lg border border-hairline bg-white p-0.5">
          {RANGES.map((d) => (
            <button key={d} onClick={() => setDays(d)} className={cn('rounded-md px-3 py-1 text-sm transition-colors', days === d ? 'bg-zinc-950 text-white' : 'text-zinc-600 hover:text-zinc-950')}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

      {/* Summary */}
      <div className="grid grid-cols-3 divide-x divide-hairline overflow-hidden rounded-2xl border border-hairline bg-white">
        {[
          { label: 'Replies', value: report?.total_replies ?? '—' },
          { label: 'Unanswered', value: report?.unanswered ?? '—' },
          { label: 'Unanswered rate', value: report ? `${pct}%` : '—' },
        ].map((s) => (
          <div key={s.label} className="px-5 py-4">
            <p className="text-xs text-zinc-500">{s.label}</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight text-zinc-950">{loading ? <span className="inline-block h-7 w-12 animate-pulse rounded bg-zinc-100" /> : s.value}</p>
          </div>
        ))}
      </div>

      {/* Unanswered */}
      <div className="overflow-hidden rounded-2xl border border-hairline bg-white">
        <div className="border-b border-hairline px-5 py-3.5">
          <h3 className="text-sm font-semibold text-zinc-950">Unanswered questions</h3>
          <p className="text-xs text-zinc-500">Grouped by wording, most asked first.</p>
        </div>
        {loading ? (
          <div className="grid place-items-center py-14"><Loader2 className="h-5 w-5 animate-spin text-zinc-400" /></div>
        ) : !report || report.questions.length === 0 ? (
          <div className="px-6 py-14 text-center">
            <div className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-600"><Check className="h-5 w-5" /></div>
            <p className="mt-3 text-sm font-medium text-zinc-900">Nothing unanswered in the last {days} days</p>
            <p className="mt-1 text-sm text-zinc-500">New gaps show up here as customers chat.</p>
          </div>
        ) : (
          <div className="divide-y divide-hairline">
            {report.questions.map((q) => (
              <div key={q.key} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start">
                <div className="min-w-0 flex-1">
                  <div className="flex items-start gap-2">
                    <MessageCircleQuestion className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                    <p className="text-sm font-medium text-zinc-950">{q.question}</p>
                  </div>
                  <p className="ml-6 mt-1 line-clamp-2 text-sm text-zinc-500">Agent: {q.sample_answer || '(no reply)'}</p>
                  <p className="ml-6 mt-1.5 text-xs text-zinc-400">
                    Asked {q.count}× {q.last_asked_at ? `· last ${formatRelative(q.last_asked_at)}` : ''}
                  </p>
                </div>
                <div className="ml-6 flex shrink-0 gap-2 sm:ml-0">
                  <button onClick={() => dismiss(q)} className="h-8 rounded-lg px-3 text-sm text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900">Dismiss</button>
                  <button
                    onClick={() => setDialog({ mode: 'new', question: q.question, originalAnswer: q.sample_answer, messageIds: q.message_ids })}
                    className="h-8 rounded-lg bg-zinc-950 px-3 text-sm font-medium text-white hover:bg-zinc-800"
                  >
                    Add answer
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Corrections */}
      <div className="overflow-hidden rounded-2xl border border-hairline bg-white">
        <div className="flex items-center justify-between border-b border-hairline px-5 py-3.5">
          <div>
            <h3 className="text-sm font-semibold text-zinc-950">Taught answers ({corrections.length})</h3>
            <p className="text-xs text-zinc-500">Stored as Q&amp;A sources. Editing re-indexes the answer.</p>
          </div>
          <button onClick={() => setDialog({ mode: 'new', question: '', messageIds: [] })} className="h-8 rounded-lg border border-hairline px-3 text-sm font-medium text-zinc-900 hover:bg-zinc-50">
            Add Q&amp;A
          </button>
        </div>
        {corrections.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-zinc-500">No taught answers yet. Use “Add answer” above, or “Improve answer” in the Inbox.</p>
        ) : (
          <div className="divide-y divide-hairline">
            {corrections.map((c) => (
              <div key={c.id} className="flex items-start gap-3 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="truncate text-sm font-medium text-zinc-950">{c.question}</p>
                    {kbBadge(c.kb_status)}
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-zinc-500">{c.answer}</p>
                </div>
                <button onClick={() => setDialog({ mode: 'edit', correction: c })} className="grid h-8 w-8 place-items-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900" aria-label="Edit">
                  <Pencil className="h-4 w-4" />
                </button>
                <button onClick={() => removeCorrection(c)} className="grid h-8 w-8 place-items-center rounded-lg text-zinc-500 hover:bg-rose-50 hover:text-rose-600" aria-label="Delete">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {dialog && (
        <CorrectionDialog
          agentId={agentId}
          question={dialog.mode === 'edit' ? dialog.correction.question : dialog.question}
          answer={dialog.mode === 'edit' ? dialog.correction.answer : ''}
          originalAnswer={dialog.mode === 'new' ? dialog.originalAnswer : undefined}
          messageIds={dialog.mode === 'new' ? dialog.messageIds : []}
          correctionId={dialog.mode === 'edit' ? dialog.correction.id : undefined}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            load();
          }}
        />
      )}
    </section>
  );
}
