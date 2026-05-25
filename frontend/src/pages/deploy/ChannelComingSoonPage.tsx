import { Navigate, useParams } from 'react-router-dom';
import { Smartphone } from 'lucide-react';
import { COMING_SOON_CHANNELS, COMING_SOON_CHANNEL_IDS } from './constants';

export default function ChannelComingSoonPage() {
  const { agentId, channel } = useParams();

  if (!channel || !COMING_SOON_CHANNEL_IDS.has(channel)) {
    return <Navigate to={`/agents/${agentId}/deploy`} replace />;
  }

  const config = COMING_SOON_CHANNELS.find((item) => item.id === channel);
  if (!config) {
    return <Navigate to={`/agents/${agentId}/deploy`} replace />;
  }

  const Icon = config.icon;

  return (
    <div className="mx-auto max-w-lg rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-8 shadow-sm sm:p-10">
      <div className={`grid h-16 w-16 place-items-center rounded-2xl text-white shadow-sm ${config.iconBg}`}>
        <Icon className="h-8 w-8" />
      </div>
      <div className="mt-8 flex items-center gap-2">
        <h2 className="text-2xl font-bold text-brand-primary">{config.title}</h2>
        {config.badge && (
          <span className="rounded-full bg-brand-primary px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-brand-on-primary">
            {config.badge}
          </span>
        )}
      </div>
      <p className="mt-4 text-sm leading-relaxed text-on-surface-variant">{config.copy}</p>
      <div className="mt-8 flex items-center gap-2">
        <button
          type="button"
          disabled
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant/40"
          aria-hidden
        >
          <Smartphone className="h-4 w-4" />
        </button>
        <button
          type="button"
          disabled
          className="h-10 flex-1 cursor-not-allowed rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm font-bold text-on-surface-variant/60"
        >
          Coming soon
        </button>
      </div>
    </div>
  );
}
