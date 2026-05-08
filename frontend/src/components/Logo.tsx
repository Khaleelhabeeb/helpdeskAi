import { cn } from '../lib/utils';

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <img 
        src="/logo_white.png" 
        alt="HelpDeskAI Logo" 
        className="w-12 h-12 object-contain"
      />
      <span className="text-xl font-bold tracking-tighter text-brand-primary leading-tight">HelpDeskAI</span>
    </div>
  );
}
