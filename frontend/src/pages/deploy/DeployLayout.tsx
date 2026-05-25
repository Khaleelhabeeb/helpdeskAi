import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { AppLayout } from '../../components/Layout';
import { DeploySubNav } from '../../components/deploy/DeploySubNav';
import { cn } from '../../lib/utils';
import { DEPLOY_CHANNELS } from './constants';
import { DeployProvider, useDeploy } from './DeployProvider';
import { WidgetDeployActions } from './WidgetDeployActions';

function DeployLayoutContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { agentId } = useParams();
  const { agent, isLoading, error, notice, setError, setNotice } = useDeploy();

  const isWidgetRoute = location.pathname.endsWith('/deploy/widget');

  const activeChannel = DEPLOY_CHANNELS.find((channel) => {
    if (channel.path === '') {
      return location.pathname === `/agents/${agentId}/deploy`;
    }
    return location.pathname.endsWith(`/deploy/${channel.path}`);
  });

  return (
    <div className="space-y-3">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => navigate(`/agents?agent=${encodeURIComponent(agentId ?? '')}`)}
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-transparent px-1.5 text-xs font-bold text-on-surface-variant transition-colors hover:border-surface-container-highest hover:bg-surface-container-low hover:text-brand-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span className="max-w-[140px] truncate sm:max-w-[200px]">{agent?.name ?? 'Agent'}</span>
          </button>

          <span className="hidden text-on-surface-variant/30 sm:inline" aria-hidden>
            /
          </span>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-bold tracking-tight text-brand-primary sm:text-xl">
              {activeChannel?.label ?? 'Deploy'}
            </h1>
          </div>

          {isWidgetRoute && !isLoading && <WidgetDeployActions />}
        </div>

        {activeChannel?.description && (
          <p className="text-xs leading-snug text-on-surface-variant sm:pl-0">
            {activeChannel.description}
          </p>
        )}
      </header>

      <DeploySubNav />

      {(error || notice) && (
        <div
          className={cn(
            'flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-xs font-medium sm:text-sm',
            error
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          )}
        >
          <span className="min-w-0 flex-1">{error || notice}</span>
          <button
            type="button"
            onClick={() => (error ? setError('') : setNotice(''))}
            className="shrink-0 text-[10px] font-bold uppercase tracking-wide underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-surface-container-highest bg-surface-container-lowest text-sm font-medium text-on-surface-variant">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading...
        </div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}

export default function DeployLayout() {
  return (
    <AppLayout compact>
      <DeployProvider>
        <DeployLayoutContent />
      </DeployProvider>
    </AppLayout>
  );
}
