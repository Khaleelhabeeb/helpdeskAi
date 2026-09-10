import type { LucideIcon } from 'lucide-react';
import { cn } from '../lib/utils';

type Icon3DProps = {
  icon: LucideIcon;
  from: string;
  to: string;
  shadow: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
};

const sizes = {
  sm: { box: 'h-14 w-14 rounded-2xl', icon: 'h-6 w-6' },
  md: { box: 'h-[72px] w-[72px] rounded-[20px]', icon: 'h-7 w-7' },
  lg: { box: 'h-20 w-20 rounded-3xl', icon: 'h-8 w-8' },
};

export function Icon3D({ icon: Icon, from, to, shadow, size = 'md', className }: Icon3DProps) {
  const s = sizes[size];

  return (
    <div
      className={cn(
        'relative flex items-center justify-center',
        s.box,
        className
      )}
      style={{
        background: `linear-gradient(145deg, ${from} 0%, ${to} 100%)`,
        boxShadow: [
          `0 12px 24px -6px ${shadow}`,
          '0 4px 8px -2px rgba(0,0,0,0.08)',
          'inset 0 1px 0 rgba(255,255,255,0.45)',
          'inset 0 -2px 4px rgba(0,0,0,0.06)',
        ].join(', '),
      }}
    >
      <div
        className="absolute inset-x-3 top-1.5 h-[35%] rounded-full opacity-30"
        style={{ background: 'linear-gradient(180deg, rgba(255,255,255,0.7), transparent)' }}
        aria-hidden
      />
      <Icon className={cn(s.icon, 'relative text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.25)]')} strokeWidth={2.25} />
    </div>
  );
}
