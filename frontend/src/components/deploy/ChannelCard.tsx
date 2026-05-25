import { Smartphone } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { Toggle } from './Toggle';

type ChannelCardProps = {
  title: string;
  description: string;
  previewGradient: string;
  preview: React.ReactNode;
  enabled: boolean;
  onToggle?: (enabled: boolean) => void;
  toggleDisabled?: boolean;
  manageTo?: string;
  manageLabel?: string;
  manageDisabled?: boolean;
  showMobileButton?: boolean;
};

export function ChannelCard({
  title,
  description,
  previewGradient,
  preview,
  enabled,
  onToggle,
  toggleDisabled,
  manageTo,
  manageLabel = 'Manage',
  manageDisabled,
  showMobileButton,
}: ChannelCardProps) {
  const manageClass = cn(
    'flex h-10 flex-1 items-center justify-center rounded-lg border border-surface-container-highest bg-surface px-4 text-sm font-bold transition-colors',
    manageDisabled
      ? 'pointer-events-none cursor-default text-on-surface-variant/50'
      : 'text-brand-primary hover:border-brand-primary/20 hover:bg-surface-container-low'
  );

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-surface-container-highest bg-surface-container-lowest shadow-sm transition-shadow hover:shadow-md">
      <div className={cn('relative h-44 shrink-0 overflow-hidden sm:h-52', previewGradient)}>
        {preview}
      </div>
      <div className="flex flex-1 flex-col p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold text-brand-primary sm:text-xl">{title}</h2>
          <Toggle checked={enabled} onChange={onToggle} disabled={toggleDisabled} />
        </div>
        <p className="mt-2 flex-1 text-sm leading-relaxed text-on-surface-variant">{description}</p>
        <div className="mt-5 flex items-center gap-2">
          {showMobileButton && (
            <button
              type="button"
              disabled
              className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant/50"
              aria-label="Mobile preview"
            >
              <Smartphone className="h-4 w-4" />
            </button>
          )}
          {manageTo && !manageDisabled ? (
            <Link to={manageTo} className={manageClass}>
              {manageLabel}
            </Link>
          ) : (
            <span className={manageClass}>{manageLabel}</span>
          )}
        </div>
      </div>
    </article>
  );
}
