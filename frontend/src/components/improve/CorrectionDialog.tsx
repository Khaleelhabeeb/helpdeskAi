import { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { apiFetch } from '../../lib/api';

export type Correction = {
  id: string;
  question: string;
  answer: string;
  kb_id: string | null;
  kb_status: 'pending' | 'ready' | 'failed' | null;
  created_at: string | null;
  updated_at: string | null;
};

type Props = {
  agentId: string;
  question: string;
  answer?: string;
  /** The reply being fixed, shown for reference */
  originalAnswer?: string;
  messageIds?: number[];
  correctionId?: string;
  onClose: () => void;
  onSaved: (correction: Correction) => void;
};

const fieldCls =
  'w-full rounded-lg border border-hairline bg-white px-3 py-2 text-sm text-zinc-900 outline-none placeholder:text-zinc-400 focus:ring-2 focus:ring-zinc-900/10';

export function CorrectionDialog({ agentId, question: q0, answer: a0 = '', originalAnswer, messageIds = [], correctionId, onClose, onSaved }: Props) {
  const [question, setQuestion] = useState(q0);
  const [answer, setAnswer] = useState(a0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setSaving(true);
    setError('');
    try {
      const saved = await apiFetch<Correction>(
        correctionId ? `/agents/${agentId}/corrections/${correctionId}` : `/agents/${agentId}/corrections`,
        {
          method: correctionId ? 'PUT' : 'POST',
          body: JSON.stringify({ question: question.trim(), answer: answer.trim(), message_ids: messageIds }),
        }
      );
      onSaved(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the answer');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[80] grid place-items-center bg-zinc-950/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl border border-hairline bg-white shadow-2xl" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="flex items-start justify-between gap-4 border-b border-hairline px-6 py-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-950">{correctionId ? 'Edit answer' : 'Teach the right answer'}</h2>
            <p className="mt-0.5 text-sm text-zinc-500">Saved as Q&amp;A knowledge — the agent uses it next time someone asks.</p>
          </div>
          <button onClick={onClose} className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-zinc-400 hover:bg-zinc-100 hover:text-zinc-900" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-6 py-5">
          {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <label className="block">
            <span className="text-sm font-medium text-zinc-900">Question</span>
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} maxLength={1000} className={`${fieldCls} mt-1.5 resize-none`} />
          </label>
          {originalAnswer && (
            <div>
              <span className="text-sm font-medium text-zinc-900">What the agent said</span>
              <p className="mt-1.5 max-h-28 overflow-y-auto rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-500">{originalAnswer}</p>
            </div>
          )}
          <label className="block">
            <span className="text-sm font-medium text-zinc-900">Correct answer</span>
            <textarea autoFocus value={answer} onChange={(e) => setAnswer(e.target.value)} rows={5} maxLength={8000} placeholder="Write the answer exactly as you'd want the agent to give it." className={`${fieldCls} mt-1.5`} />
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-hairline px-6 py-4">
          <button onClick={onClose} className="h-9 rounded-lg border border-hairline px-4 text-sm font-medium text-zinc-900 hover:bg-zinc-50">Cancel</button>
          <button onClick={save} disabled={saving || question.trim().length < 3 || !answer.trim()} className="inline-flex h-9 items-center gap-2 rounded-lg bg-zinc-950 px-4 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-40">
            {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save answer
          </button>
        </div>
      </div>
    </div>
  );
}
