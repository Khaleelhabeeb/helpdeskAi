import {
  BarChart3,
  BookOpen,
  Bot,
  CreditCard,
  Database,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  Users,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'motion/react';
import { cn } from '../lib/utils';
import { Logo } from './Logo';
import { useAuth } from '../lib/auth';

const SIDEBAR_EXPANDED = 248;
const SIDEBAR_COLLAPSED = 64;

type NavItem = { icon: typeof LayoutDashboard; label: string; path: string };

const primaryNav: NavItem[] = [
  { icon: LayoutDashboard, label: 'Overview', path: '/dashboard' },
  { icon: Bot, label: 'Agents', path: '/agents' },
  { icon: Database, label: 'Knowledge', path: '/knowledge' },
  { icon: Inbox, label: 'Inbox', path: '/inbox' },
  { icon: BarChart3, label: 'Analytics', path: '/analytics' },
  { icon: Users, label: 'Team', path: '/team' },
  { icon: CreditCard, label: 'Usage', path: '/billing' },
];

const secondaryNav: NavItem[] = [
  { icon: BookOpen, label: 'Guides', path: '/guides' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

function userInitials(email?: string) {
  if (!email) return 'U';
  const local = email.split('@')[0] ?? '';
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return local.slice(0, 2).toUpperCase() || 'U';
}

function NavTooltip({ label, show }: { label: string; show: boolean }) {
  if (!show) return null;
  return (
    <span
      className={cn(
        'pointer-events-none absolute left-[calc(100%+12px)] top-1/2 z-[100] -translate-y-1/2',
        'whitespace-nowrap rounded-md bg-zinc-900 px-2.5 py-1.5',
        'text-xs font-medium text-white shadow-lg',
        'opacity-0 transition-opacity duration-150',
        'group-hover/nav:opacity-100 group-focus-within/nav:opacity-100'
      )}
      role="tooltip"
    >
      {label}
    </span>
  );
}

function NavLinkItem({
  item,
  isCompact,
  onClose,
}: {
  item: NavItem;
  isCompact: boolean;
  onClose?: () => void;
}) {
  return (
    <NavLink
      to={item.path}
      onClick={onClose}
      title={isCompact ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          'group/nav relative flex items-center transition-colors',
          isCompact
            ? 'mx-auto h-9 w-9 justify-center rounded-lg text-sm'
            : 'justify-between rounded-lg px-2.5 py-[7px] text-[14px]',
          isActive
            ? 'bg-white font-medium text-zinc-950 shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_1px_3px_rgba(0,0,0,0.06)]'
            : 'text-zinc-600 hover:bg-zinc-900/[0.04] hover:text-zinc-950'
        )
      }
    >
      {({ isActive }) => (
        <>
          <span className={cn('flex items-center', isCompact ? 'justify-center' : 'gap-3 min-w-0')}>
            <item.icon
              className={cn(
                'shrink-0',
                'h-[18px] w-[18px]',
                isActive ? 'text-zinc-950' : 'text-zinc-400 group-hover/nav:text-zinc-700'
              )}
              strokeWidth={2}
            />
            {!isCompact && <span className="truncate">{item.label}</span>}
          </span>
          <NavTooltip label={item.label} show={isCompact} />
        </>
      )}
    </NavLink>
  );
}

type SidebarProps = {
  className?: string;
  onClose?: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  showCollapseControl?: boolean;
};

export function Sidebar({
  className,
  onClose,
  collapsed = false,
  onToggleCollapsed,
  showCollapseControl = true,
}: SidebarProps) {
  const { signOut, user } = useAuth();
  const isCompact = collapsed && showCollapseControl;

  return (
    <aside
      className={cn(
        'relative flex h-full flex-col bg-canvas',
        'overflow-hidden',
        'border-r border-hairline',
        className
      )}
    >
      <div className={cn('flex h-full flex-col', isCompact ? 'px-2 py-4' : 'px-3 py-5')}>
        {/* Brand */}
        <div className={cn('flex items-center', isCompact ? 'justify-center' : 'justify-between gap-2')}>
          <div className={cn('flex items-center min-w-0', isCompact ? 'justify-center' : 'gap-2.5')}>
            <Logo compact={isCompact} />
          </div>
          {showCollapseControl && onToggleCollapsed && !isCompact && (
            <button
              type="button"
              onClick={onToggleCollapsed}
              className="grid h-7 w-7 place-items-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          )}
        </div>

        {showCollapseControl && onToggleCollapsed && isCompact && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            className="mx-auto mt-4 grid h-8 w-8 place-items-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        )}

        {/* Primary action */}
        <NavLink
          to="/agents"
          onClick={onClose}
          title={isCompact ? 'New agent' : undefined}
          className={cn(
            'group/nav relative flex items-center text-sm font-semibold transition-colors',
            isCompact
              ? 'mx-auto mt-5 h-9 w-9 justify-center rounded-lg bg-zinc-950 text-white hover:bg-zinc-800'
              : 'mt-5 justify-center gap-2 rounded-lg bg-zinc-950 px-3 py-2 font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_2px_rgba(0,0,0,0.2)] hover:bg-zinc-800'
          )}
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!isCompact && <span>New agent</span>}
          <NavTooltip label="New agent" show={isCompact} />
        </NavLink>

        {/* Primary nav */}
        <nav className={cn('flex-1 overflow-y-auto', isCompact ? 'mt-5 space-y-1' : 'mt-5 space-y-1')}>
          {primaryNav.map((item) => (
            <NavLinkItem key={item.path} item={item} isCompact={isCompact} onClose={onClose} />
          ))}

          {!isCompact && (
            <p className="px-2.5 pb-1 pt-5 text-xs font-medium text-zinc-400">
              Workspace
            </p>
          )}
          {secondaryNav.map((item) => (
            <NavLinkItem key={item.path} item={item} isCompact={isCompact} onClose={onClose} />
          ))}
        </nav>

        {/* Sign out */}
        <div className={cn('border-t border-hairline', isCompact ? 'pt-4' : 'pt-3')}>
          <button
            type="button"
            onClick={() => {
              signOut();
              onClose?.();
            }}
            title={isCompact ? 'Sign out' : undefined}
            className={cn(
              'group/nav relative flex items-center transition-colors',
              isCompact
                ? 'mx-auto h-9 w-9 justify-center rounded-lg text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700'
                : 'w-full gap-3 rounded-lg px-2.5 py-2 text-[14px] font-medium text-zinc-600 hover:bg-zinc-900/[0.04] hover:text-zinc-950'
            )}
          >
            <LogOut className="h-[18px] w-[18px] shrink-0 text-zinc-500 group-hover/nav:text-zinc-700" strokeWidth={2} />
            {!isCompact && <span>Sign out</span>}
            <NavTooltip label="Sign out" show={isCompact} />
          </button>
        </div>

        {/* User */}
        <div
          className={cn(
            'flex items-center border-t border-hairline',
            isCompact ? 'mx-auto mt-4 h-9 w-9 justify-center border-0 pt-0' : 'mt-3 gap-3 px-1.5 py-3'
          )}
          title={isCompact ? user?.email : undefined}
        >
          <div className="grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-full bg-zinc-900 text-white">
            <span className="text-[11px] font-semibold">{userInitials(user?.email)}</span>
          </div>
          {!isCompact && (
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold leading-none text-zinc-900">
                {user?.email?.split('@')[0] ?? 'Account'}
              </p>
              <p className="mt-1 truncate text-xs leading-none text-zinc-500">{user?.email ?? '—'}</p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}

export function DesktopSidebar({
  collapsed,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      className="fixed left-0 top-0 z-50 hidden h-full md:block"
    >
      <div className="h-full overflow-hidden border-r border-hairline bg-canvas">
        <Sidebar
          collapsed={collapsed}
          onToggleCollapsed={onToggleCollapsed}
          className="h-full w-full border-0"
        />
      </div>
    </motion.aside>
  );
}

export { SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED };

type TopAppBarProps = {
  onMenuClick?: () => void;
};

const TITLE_BY_PATH: Array<[RegExp, string]> = [
  [/\/dashboard/, 'Overview'],
  [/\/agents\/.*\/deploy/, 'Deploy'],
  [/\/agents/, 'Agents'],
  [/\/knowledge/, 'Knowledge'],
  [/\/inbox/, 'Inbox'],
  [/\/analytics/, 'Analytics'],
  [/\/team/, 'Team'],
  [/\/billing/, 'Usage'],
  [/\/guides/, 'Guides'],
  [/\/settings/, 'Settings'],
];

export function TopAppBar({ onMenuClick }: TopAppBarProps) {
  const location = useLocation();
  const { user } = useAuth();

  const pageTitle = TITLE_BY_PATH.find(([re]) => re.test(location.pathname))?.[1] ?? 'Workspace';

  return (
    <header className="sticky top-0 z-40 flex h-14 w-full items-center justify-between gap-3 border-b border-hairline bg-canvas/85 px-3 backdrop-blur-md md:h-16 md:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="grid h-9 w-9 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="hidden min-w-0 sm:block">
          <p className="flex items-center gap-2 truncate text-sm">
            <span className="text-zinc-400">Workspace</span>
            <span className="text-zinc-300">/</span>
            <span className="font-medium text-zinc-950">{pageTitle}</span>
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <div
          className="grid h-8 w-8 place-items-center rounded-full bg-zinc-900 text-xs font-semibold text-white"
          title={user?.email}
        >
          {userInitials(user?.email)}
        </div>
      </div>
    </header>
  );
}
