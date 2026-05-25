import { ArrowUp } from 'lucide-react';

export function HelpPageMiniPreview({ name }: { name: string }) {
  return (
    <div className="pointer-events-none absolute bottom-5 left-1/2 w-[92%] max-w-[280px] -translate-x-1/2">
      <div className="overflow-hidden rounded-xl bg-zinc-950 shadow-2xl ring-1 ring-black/15">
        <div className="flex items-center gap-1.5 border-b border-zinc-800 bg-zinc-900 px-3 py-2">
          <span className="h-2 w-2 rounded-full bg-red-500/80" />
          <span className="h-2 w-2 rounded-full bg-amber-400/80" />
          <span className="h-2 w-2 rounded-full bg-emerald-500/80" />
          <div className="ml-2 flex items-center gap-1.5">
            <span className="grid h-5 w-5 place-items-center rounded bg-white text-[8px] font-black text-black">
              {name.slice(0, 2).toUpperCase()}
            </span>
            <span className="text-[10px] font-bold text-zinc-300">{name}</span>
          </div>
        </div>
        <div className="px-4 py-6 text-center">
          <h3 className="text-sm font-bold text-white">Hey, I&apos;m {name}</h3>
          <p className="mt-4 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-left text-[10px] text-zinc-500">
            Ask me anything...
          </p>
          <div className="mt-3 flex justify-end">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-white text-black">
              <ArrowUp className="h-3.5 w-3.5" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
