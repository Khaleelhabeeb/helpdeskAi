import type { LucideIcon } from 'lucide-react';
import { Smartphone } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '../../lib/utils';

export function ComingSoonCard({
  title,
  copy,
  icon: Icon,
  iconBg,
  badge,
  detailTo,
}: {
  title: string;
  copy: string;
  icon: LucideIcon;
  iconBg: string;
  badge?: string;
  detailTo?: string;
}) {
  return (
    <article className="flex flex-col rounded-2xl border border-surface-container-highest bg-surface-container-lowest p-6 shadow-sm sm:p-8">
      <div className={cn('grid h-14 w-14 place-items-center rounded-2xl text-white shadow-sm', iconBg)}>
        <Icon className="h-7 w-7" />
      </div>
      <div className="mt-8 flex items-center gap-2">
        <h2 className="text-xl font-bold text-brand-primary">{title}</h2>
        {badge && (
          <span className="rounded-full bg-brand-primary px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide text-brand-on-primary">
            {badge}
          </span>
        )}
      </div>
      <p className="mt-3 min-h-[4.5rem] flex-1 text-sm leading-relaxed text-on-surface-variant">{copy}</p>
      <div className="mt-6 flex items-center gap-2">
        <button
          type="button"
          disabled
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant/40"
          aria-hidden
        >
          <Smartphone className="h-4 w-4" />
        </button>
        {detailTo ? (
          <Link
            to={detailTo}
            className="flex h-10 flex-1 items-center justify-center rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm font-bold text-on-surface-variant transition-colors hover:border-brand-primary/20 hover:text-brand-primary"
          >
            Coming soon
          </Link>
        ) : (
          <button
            type="button"
            disabled
            className="h-10 flex-1 cursor-not-allowed rounded-lg border border-surface-container-highest bg-surface-container-low px-4 text-sm font-bold text-on-surface-variant/60"
          >
            Coming soon
          </button>
        )}
      </div>
    </article>
  );
}
