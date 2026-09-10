import { cn } from '../lib/utils';

type LogoProps = {
  className?: string;
  compact?: boolean;
  theme?: 'light' | 'dark';
};

export function Logo({ className, compact = false, theme = 'dark' }: LogoProps) {
  return (
    <div
      className={cn(
        'flex items-center',
        compact ? 'justify-center' : 'gap-2.5',
        className
      )}
    >
      <img
        src={theme === 'light' ? '/logo_white.png' : '/logo_black.png'}
        alt="HelpDeskAI"
        className={cn('shrink-0 object-contain', compact ? 'h-9 w-9' : 'h-8 w-8')}
      />
      {!compact && (
        <span className={cn(
          'truncate text-[15px] font-bold tracking-tight leading-none',
          theme === 'light' ? 'text-white' : 'text-[#1a1a1a]'
        )}>
          helpdesk<span className="text-[#ef5f3d]">ai</span>
        </span>
      )}
    </div>
  );
}
