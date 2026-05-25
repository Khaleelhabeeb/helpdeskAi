import { NavLink, useParams } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { DEPLOY_CHANNELS } from '../../pages/deploy/constants';

export function DeploySubNav() {
  const { agentId } = useParams();

  return (
    <nav className="-mx-0.5 flex gap-0.5 overflow-x-auto rounded-lg border border-surface-container-highest bg-surface-container-low p-0.5 scrollbar-none">
      {DEPLOY_CHANNELS.map((channel) => {
        const to =
          channel.path === ''
            ? `/agents/${agentId}/deploy`
            : `/agents/${agentId}/deploy/${channel.path}`;

        return (
          <NavLink
            key={channel.id}
            to={to}
            end={channel.path === ''}
            className={({ isActive }) =>
              cn(
                'flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors sm:gap-2 sm:px-3 sm:py-2 sm:text-sm',
                isActive
                  ? 'bg-brand-primary text-brand-on-primary shadow-sm'
                  : 'text-on-surface-variant hover:bg-surface-container-lowest hover:text-brand-primary'
              )
            }
          >
            <channel.icon className="h-4 w-4 shrink-0" />
            <span>{channel.label}</span>
            {channel.status === 'soon' && (
              <span
                className={cn(
                  'rounded px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wide',
                  'bg-surface-container-high text-on-surface-variant'
                )}
              >
                Soon
              </span>
            )}
            {channel.status === 'preview' && (
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wide text-amber-800">
                Preview
              </span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}
