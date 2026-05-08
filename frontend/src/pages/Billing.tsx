import { ArrowRight, FileText, Loader2, TrendingUp } from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { useEffect, useMemo, useState } from 'react';
import { apiFetch, CreditsInfo, formatDate } from '../lib/api';

export default function Billing() {
  const [credits, setCredits] = useState<CreditsInfo | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadCredits() {
    setLoading(true);
    setError('');
    try {
      setCredits(await apiFetch<CreditsInfo>('/users/credits'));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load usage data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCredits();
  }, []);

  const totalUsed = useMemo(() => {
    if (!credits) return 0;
    return Math.max(0, credits.max_credits - credits.credits_remaining);
  }, [credits]);

  return (
    <AppLayout>
      <div className="space-y-12">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Usage</h1>
          <p className="text-on-surface-variant mt-1 text-sm">Plans are disabled for now, so every workspace has full access.</p>
        </header>

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="min-h-[260px] flex items-center justify-center text-on-surface-variant">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading usage...
          </div>
        ) : credits && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex flex-col bg-surface-container-lowest border border-surface-container-highest rounded-xl overflow-hidden group hover:border-brand-primary transition-colors">
              <div className="p-8 border-b border-surface-container-highest flex flex-col sm:flex-row gap-6 justify-between items-start">
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <h2 className="text-3xl font-bold text-brand-primary">Full Access</h2>
                    <span className="bg-brand-primary text-brand-on-primary px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest leading-none">Active</span>
                  </div>
                  <p className="text-sm text-on-surface-variant">Usage tracking resets on <span className="font-bold text-brand-primary">{formatDate(credits.next_reset_date)}</span>.</p>
                </div>
                <div className="text-left sm:text-right">
                  <div className="text-4xl font-bold text-brand-primary">{totalUsed.toLocaleString()}</div>
                  <div className="text-sm font-normal text-on-surface-variant">tracked requests</div>
                </div>
              </div>
              <div className="p-8 bg-surface-container-low">
                <div className="rounded-xl border border-surface-container-highest bg-surface-container-lowest p-6">
                  <div className="text-sm font-black uppercase tracking-widest text-brand-primary">No plan limits</div>
                  <p className="mt-2 text-sm text-on-surface-variant">Agent count, knowledge uploads, and chat usage are not blocked by free/paid/pro tiers.</p>
                </div>
              </div>
            </div>

            <div className="flex flex-col bg-surface-container-lowest border border-surface-container-highest rounded-xl p-8 group hover:border-brand-primary transition-colors">
              <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-6 pb-2 border-b border-surface-container-highest flex items-center justify-between">
                Agent Usage
                <FileText className="w-4 h-4 opacity-40 group-hover:opacity-100 transition-opacity" />
              </h3>
              <div className="flex-1 space-y-5">
                {credits.agent_usage.length ? credits.agent_usage.map((usage) => (
                  <div key={usage.agent_id} className="flex items-center justify-between text-xs text-brand-primary">
                    <span className="font-bold truncate">{usage.agent_name}</span>
                    <span className="font-mono text-on-surface-variant">{usage.credits_used.toLocaleString()} requests</span>
                  </div>
                )) : (
                  <p className="text-sm text-on-surface-variant">No agent usage recorded this cycle.</p>
                )}
              </div>
              <button onClick={loadCredits} className="mt-8 text-left text-[10px] font-bold uppercase tracking-widest text-brand-primary hover:translate-x-1 transition-transform flex items-center gap-2">
                Refresh Usage <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="lg:col-span-3 flex flex-col bg-surface-container-lowest border border-surface-container-highest rounded-xl p-8 hover:border-brand-primary transition-colors">
              <div className="flex items-center gap-3 mb-10">
                <TrendingUp className="w-5 h-5 text-brand-primary" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-brand-primary">Current Cycle</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="rounded-lg border border-surface-container-highest bg-surface p-5">
                  <div className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Requests tracked</div>
                  <div className="mt-3 text-2xl font-bold text-brand-primary">{totalUsed.toLocaleString()}</div>
                </div>
                <div className="rounded-lg border border-surface-container-highest bg-surface p-5">
                  <div className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Remaining</div>
                  <div className="mt-3 text-2xl font-bold text-brand-primary">Unlimited</div>
                </div>
                <div className="rounded-lg border border-surface-container-highest bg-surface p-5">
                  <div className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Reset window</div>
                  <div className="mt-3 text-2xl font-bold text-brand-primary">{credits.days_until_reset} days</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
