import {
  MessageSquare,
  Bot,
  Database,
  ShieldCheck,
  TrendingUp,
  ArrowUpRight,
  Loader2,
} from 'lucide-react';
import { AppLayout } from '../components/Layout';
import { cn } from '../lib/utils';
import { useEffect, useMemo, useState } from 'react';
import { Agent, apiFetch, CreditsInfo, formatRelative } from '../lib/api';

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

export default function Dashboard() {
  const [data, setData] = useState<DashboardData>({
    agents: [],
    credits: null,
    interactions: null,
    activity: null,
    knowledgeCount: 0,
  });
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError('');
      try {
        const summary = await apiFetch<DashboardData>('/dashboard/summary');
        if (!cancelled) {
          setData(summary);
        }
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

  const metrics = useMemo(() => {
    const totalQuestions = data.interactions?.total_questions ?? 0;
    const creditsUsed = data.credits ? data.credits.max_credits - data.credits.credits_remaining : 0;

    return [
      { label: 'Messages this month', value: totalQuestions.toLocaleString(), icon: MessageSquare, sub: `${creditsUsed.toLocaleString()} requests tracked`, trend: totalQuestions > 0 ? 'up' : 'neutral' },
      { label: 'Active Agents', value: data.agents.length.toLocaleString(), icon: Bot, sub: data.interactions?.most_active_agent ? `Top: ${data.interactions.most_active_agent}` : 'Ready to configure', trend: 'neutral' },
      { label: 'Knowledge Sources', value: data.knowledgeCount.toLocaleString(), icon: Database, sub: 'Across your agents', trend: 'neutral' },
      { label: 'Access', value: 'Full', icon: ShieldCheck, sub: 'No tier limits', trend: 'neutral' },
    ];
  }, [data]);

  return (
    <AppLayout>
      <div className="space-y-12">
        <header>
          <h1 className="text-3xl font-bold tracking-tight text-brand-primary">Overview</h1>
          <p className="text-on-surface-variant mt-1 text-sm">System status and operational metrics.</p>
        </header>

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="min-h-[260px] flex items-center justify-center text-on-surface-variant">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading dashboard...
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {metrics.map((metric) => (
                <div key={metric.label} className="bg-surface-container-lowest border border-surface-container-highest rounded-xl p-6 flex flex-col justify-between hover:border-brand-primary transition-colors group">
                  <div className="flex justify-between items-start mb-6">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{metric.label}</span>
                    <metric.icon className="w-5 h-5 text-on-surface-variant opacity-40 group-hover:text-brand-primary group-hover:opacity-100 transition-all" />
                  </div>
                  <div>
                    <div className="text-3xl font-bold text-brand-primary">{metric.value}</div>
                    <div className="flex items-center gap-1.5 mt-2 text-[11px] font-medium text-brand-inverse-primary border border-surface-container shadow-sm px-2 py-0.5 rounded-full w-fit">
                      {metric.trend === 'up' && <ArrowUpRight className="w-3 h-3 text-green-500" />}
                      {metric.sub}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-surface-container-lowest border border-surface-container-highest rounded-xl overflow-hidden">
              <div className="p-6 border-b border-surface-container-highest flex justify-between items-center">
                <h3 className="text-lg font-bold text-brand-primary">Recent Conversations</h3>
                <div className="text-xs font-bold uppercase tracking-widest text-on-surface-variant border border-surface-container-highest px-3 py-1.5 rounded-lg">
                  {data.activity?.peak_usage_hour == null ? 'No peak yet' : `Peak ${data.activity.peak_usage_hour}:00`}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-surface-container-low text-[10px] font-bold uppercase tracking-widest text-on-surface-variant border-b border-surface-container-highest">
                      <th className="px-6 py-4 font-bold">Question</th>
                      <th className="px-6 py-4 font-bold">Agent</th>
                      <th className="px-6 py-4 font-bold">Response</th>
                      <th className="px-6 py-4 font-bold text-right">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm divide-y divide-surface-container-highest">
                    {data.activity?.recent_activity.length ? data.activity.recent_activity.map((activity, index) => (
                      <tr key={`${activity.timestamp}-${index}`} className="hover:bg-surface-container-low transition-colors group">
                        <td className="px-6 py-4 font-medium text-brand-primary max-w-[260px] truncate">{activity.question || 'Customer message'}</td>
                        <td className="px-6 py-4 text-on-surface-variant">{activity.agent_name}</td>
                        <td className="px-6 py-4">
                          <span className={cn('inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-bold uppercase tracking-wider', activity.response ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : 'bg-surface-container-low text-on-surface-variant border-surface-container-highest')}>
                            {activity.response ? 'Answered' : 'Pending'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-right font-mono text-xs text-on-surface-variant opacity-60 group-hover:opacity-100 transition-opacity">
                          {formatRelative(activity.timestamp)}
                        </td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan={4} className="px-6 py-10 text-center text-sm text-on-surface-variant">
                          No conversations have been logged yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
}
