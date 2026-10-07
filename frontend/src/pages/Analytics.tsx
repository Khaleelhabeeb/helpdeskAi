import { BarChart3, Loader2, MessageSquare, RefreshCw } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { AppLayout } from '../components/Layout';
import { apiFetch } from '../lib/api';

type TeamAnalytics = {
  total: number;
  by_status: Record<string, number>;
  cases_closed: number;
  active: number;
  queued: number;
  human: number;
  by_human: Array<{ id: string; email: string; name?: string | null; total: number; queued: number; human: number; resolved: number }>;
  by_agent: Array<{ id: string; name: string; total: number; by_status: Record<string, number> }>;
};

type Summary = { interactions: { total_questions: number } | null };
type Engagement = { days_active: number; avg_questions_per_day: number };
type Credits = { usage_trend: Record<string, number> };

function StatusPill({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-surface-container-highest bg-zinc-50 px-3 py-2">
      <span className="text-xs font-medium capitalize text-on-surface-variant">{label.replace('_', ' ')}</span>
      <span className="text-sm font-bold text-brand-primary">{count}</span>
    </div>
  );
}

export default function Analytics() {
  const [team, setTeam] = useState<TeamAnalytics | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [engagement, setEngagement] = useState<Engagement | null>(null);
  const [credits, setCredits] = useState<Credits | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [t, s, e, c] = await Promise.all([
        apiFetch<TeamAnalytics>('/owner/team/analytics', { cacheMs: 0, dedupe: false }),
        apiFetch<Summary>('/dashboard/summary').catch(() => null),
        apiFetch<Engagement>('/kpi/engagement').catch(() => null),
        apiFetch<Credits>('/kpi/credits').catch(() => null),
      ]);
      setTeam(t);
      setSummary(s);
      setEngagement(e);
      setCredits(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load analytics');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const trend = useMemo(() => {
    const raw = credits?.usage_trend ?? {};
    const entries = Object.entries(raw)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-30);
    const max = Math.max(1, ...entries.map(([, v]) => v));
    return { entries, max };
  }, [credits]);

  const totalMessages = summary?.interactions?.total_questions ?? 0;

  return (
    <AppLayout>
      <div className="space-y-6">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Analytics</h1>
            <p className="mt-1 text-sm text-on-surface-variant">How your agents perform across support, sales, and product conversations.</p>
          </div>
          <button onClick={load} className="inline-flex h-10 items-center gap-2 rounded-lg border border-surface-container-highest bg-white px-4 text-sm font-semibold text-brand-primary hover:bg-zinc-50">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
        </header>

        {error && <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

        {loading ? (
          <div className="flex min-h-[260px] items-center justify-center text-sm text-on-surface-variant">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading analytics…
          </div>
        ) : (
          <>
            {/* Stat cards */}
            <section className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              {[
                { label: 'Conversations', value: team?.total ?? 0 },
                { label: 'Resolved', value: team?.cases_closed ?? 0 },
                { label: 'Queued', value: team?.queued ?? 0 },
                { label: 'With human', value: team?.human ?? 0 },
                { label: 'Messages', value: totalMessages },
              ].map((s) => (
                <div key={s.label} className="rounded-xl border border-surface-container-highest bg-white p-5">
                  <p className="text-3xl font-bold text-brand-primary">{s.value.toLocaleString()}</p>
                  <p className="mt-1 text-sm text-on-surface-variant">{s.label}</p>
                </div>
              ))}
            </section>

            {/* Status breakdown + trend */}
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-xl border border-surface-container-highest bg-white p-5">
                <h2 className="mb-4 flex items-center gap-2 text-sm font-bold text-brand-primary">
                  <BarChart3 className="h-4 w-4" /> Status breakdown
                </h2>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(team?.by_status ?? {}).map(([k, v]) => (
                    <StatusPill key={k} label={k} count={v} />
                  ))}
                  {Object.keys(team?.by_status ?? {}).length === 0 && (
                    <p className="col-span-2 text-sm text-on-surface-variant">No conversations yet.</p>
                  )}
                </div>
              </section>

              <section className="rounded-xl border border-surface-container-highest bg-white p-5">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="flex items-center gap-2 text-sm font-bold text-brand-primary">
                    <MessageSquare className="h-4 w-4" /> Usage (last 30 days)
                  </h2>
                  {engagement && (
                    <span className="text-xs text-on-surface-variant">
                      {engagement.days_active} active days · avg {engagement.avg_questions_per_day.toFixed(1)}/day
                    </span>
                  )}
                </div>
                {trend.entries.length === 0 ? (
                  <p className="py-10 text-center text-sm text-on-surface-variant">No usage data yet.</p>
                ) : (
                  <div className="flex h-32 items-end gap-1">
                    {trend.entries.map(([day, count]) => (
                      <div key={day} className="group relative flex-1">
                        <div
                          className="rounded-t bg-zinc-200 transition-colors group-hover:bg-zinc-900"
                          style={{ height: `${Math.max(6, (count / trend.max) * 100)}%` }}
                          title={`${day}: ${count}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>

            {/* Per agent + per human */}
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-xl border border-surface-container-highest bg-white p-5">
                <h2 className="mb-4 text-sm font-bold text-brand-primary">Per AI agent</h2>
                <div className="space-y-2">
                  {(team?.by_agent ?? []).length === 0 ? (
                    <p className="text-sm text-on-surface-variant">No agents yet.</p>
                  ) : (
                    team!.by_agent.map((a) => (
                      <div key={a.id} className="rounded-lg border border-surface-container-highest bg-zinc-50 px-3 py-2.5">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-brand-primary">{a.name}</span>
                          <span className="text-xs font-bold text-on-surface-variant">{a.total} conversations</span>
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {Object.entries(a.by_status).map(([k, v]) => (
                            <span key={k} className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-on-surface-variant ring-1 ring-surface-container-highest">
                              {k.replace('_', ' ')}: {v}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>

              <section className="rounded-xl border border-surface-container-highest bg-white p-5">
                <h2 className="mb-4 text-sm font-bold text-brand-primary">Per human agent</h2>
                <div className="space-y-2">
                  {(team?.by_human ?? []).length === 0 ? (
                    <p className="text-sm text-on-surface-variant">No human agents yet.</p>
                  ) : (
                    team!.by_human.map((h) => (
                      <div key={h.id} className="flex items-center justify-between rounded-lg border border-surface-container-highest bg-zinc-50 px-3 py-2.5">
                        <div className="min-w-0">
                          <span className="block truncate text-sm font-semibold text-brand-primary">{h.name || h.email.split('@')[0]}</span>
                          <span className="text-xs text-on-surface-variant">{h.email}</span>
                        </div>
                        <div className="flex shrink-0 gap-2 text-xs font-semibold">
                          <span className="text-amber-700">{h.queued} queued</span>
                          <span className="text-sky-700">{h.human} active</span>
                          <span className="text-emerald-700">{h.resolved} closed</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </section>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
