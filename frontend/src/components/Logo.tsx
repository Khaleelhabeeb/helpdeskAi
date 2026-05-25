import { cn } from '../lib/utils';

type LogoProps = {
  className?: string;
  compact?: boolean;
};

export function Logo({ className, compact = false }: LogoProps) {
  return (
    <div
      className={cn(
        'flex items-center',
        compact ? 'justify-center' : 'gap-3',
        className
      )}
    >
      <img
        src="/logo_white.png"
        alt="HelpDeskAI"
        className={cn('shrink-0 object-contain', compact ? 'h-9 w-9' : 'h-10 w-10')}
      />
      {!compact && (
        <div className="min-w-0">
          <span className="block truncate text-base font-bold tracking-tight text-brand-primary leading-none">
            HelpDeskAI
          </span>
          <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-[0.2em] text-on-surface-variant/70">
            Support
          </span>
        </div>
      )}
    </div>
  );
}
