import { cn } from '../../lib/utils';

export function AgentAvatar({
  name,
  image,
  className,
}: {
  name: string;
  image?: string | null;
  className?: string;
}) {
  if (image) {
    return <img src={image} alt="" className={cn('h-full w-full object-cover', className)} />;
  }
  return (
    <span className={cn('text-xs font-black', className)}>
      {name.slice(0, 2).toUpperCase() || 'AI'}
    </span>
  );
}
