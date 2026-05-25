import { ArrowUp, Check } from 'lucide-react';
import { cn } from '../../lib/utils';
import { AgentAvatar } from './AgentAvatar';

export function WidgetLivePreview({
  displayName,
  logoUrl,
  theme,
  primaryColor,
  messages,
  fallbackGreeting,
}: {
  displayName: string;
  logoUrl?: string | null;
  theme: 'light' | 'dark';
  primaryColor: string;
  messages: string[];
  fallbackGreeting: string;
}) {
  const dark = theme === 'dark';
  const sendTextColor = primaryColor.toLowerCase() === '#ffffff' ? '#111111' : '#ffffff';
  const previewMessages = messages.length ? messages : [fallbackGreeting];

  return (
    <div
      className={cn(
        'h-[520px] w-full overflow-hidden rounded-[28px] shadow-2xl',
        dark ? 'bg-black text-white' : 'bg-white text-black'
      )}
    >
      <div className={cn('flex h-16 items-center gap-3 px-5', dark ? 'bg-zinc-900' : 'bg-zinc-100')}>
        <div className="grid h-10 w-10 place-items-center overflow-hidden rounded-full bg-white text-black">
          <AgentAvatar name={displayName} image={logoUrl} />
        </div>
        <div className="font-bold">{displayName}</div>
        <Check className="ml-auto h-5 w-5 text-emerald-500" />
      </div>
      <div className="flex h-[calc(100%-4rem)] flex-col p-5">
        <div className="flex-1 space-y-3 overflow-y-auto">
          {previewMessages.map((message, index) => (
            <div
              key={`${message}-${index}`}
              className={cn(
                'max-w-[78%] rounded-2xl px-4 py-3 text-sm',
                dark ? 'bg-zinc-900 text-zinc-100' : 'bg-zinc-100 text-zinc-900'
              )}
            >
              {message}
            </div>
          ))}
          <div
            className="ml-auto w-fit rounded-2xl px-4 py-2.5 text-sm"
            style={{ backgroundColor: primaryColor, color: sendTextColor }}
          >
            Thanks, I need help.
          </div>
        </div>
        <div
          className={cn(
            'mt-4 flex h-12 items-center gap-3 rounded-full border px-4',
            dark ? 'border-zinc-700' : 'border-zinc-200'
          )}
        >
          <span className={cn('flex-1 text-sm', dark ? 'text-zinc-500' : 'text-zinc-400')}>Message...</span>
          <span
            className="grid h-9 w-9 place-items-center rounded-full"
            style={{ backgroundColor: primaryColor, color: sendTextColor }}
          >
            <ArrowUp className="h-4 w-4" />
          </span>
        </div>
      </div>
    </div>
  );
}
