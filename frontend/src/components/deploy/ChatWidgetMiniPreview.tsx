import { cn } from '../../lib/utils';
import { AgentAvatar } from './AgentAvatar';

export function ChatWidgetMiniPreview({
  name,
  logoUrl,
  greeting,
  theme,
  primaryColor,
}: {
  name: string;
  logoUrl?: string | null;
  greeting: string;
  theme: 'light' | 'dark';
  primaryColor: string;
}) {
  const dark = theme === 'dark';
  const sendColor = primaryColor.toLowerCase() === '#ffffff' ? '#111' : '#fff';

  return (
    <div className="pointer-events-none absolute bottom-6 left-1/2 w-[88%] max-w-[220px] -translate-x-1/2">
      <div
        className={cn(
          'overflow-hidden rounded-2xl shadow-2xl ring-1 ring-black/10',
          dark ? 'bg-zinc-950 text-white' : 'bg-white text-zinc-900'
        )}
      >
        <div
          className={cn(
            'flex items-center gap-2 border-b px-3 py-2.5',
            dark ? 'border-zinc-800 bg-zinc-900' : 'border-zinc-200 bg-zinc-50'
          )}
        >
          <div className="grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-full bg-white text-black">
            <AgentAvatar name={name} image={logoUrl} />
          </div>
          <span className="truncate text-xs font-bold">{name}</span>
        </div>
        <div className="space-y-2 p-3">
          <div
            className={cn(
              'max-w-[90%] rounded-xl px-3 py-2 text-[11px] leading-snug',
              dark ? 'bg-zinc-900' : 'bg-zinc-100'
            )}
          >
            {greeting}
          </div>
          <div
            className="ml-auto w-fit max-w-[75%] rounded-full px-3 py-1.5 text-[10px] font-medium"
            style={{ backgroundColor: primaryColor, color: sendColor }}
          >
            I need help
          </div>
        </div>
        <div
          className={cn(
            'mx-3 mb-3 flex h-8 items-center rounded-full border px-3',
            dark ? 'border-zinc-700' : 'border-zinc-200'
          )}
        >
          <span className={cn('text-[10px]', dark ? 'text-zinc-500' : 'text-zinc-400')}>Message...</span>
        </div>
      </div>
    </div>
  );
}
