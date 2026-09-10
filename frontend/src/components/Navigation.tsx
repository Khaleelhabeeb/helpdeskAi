import {
  Bot,
  CreditCard,
  Settings,
  Plus,
  LayoutDashboard,
  HelpCircle,
  LogOut,
  Search,
  Bell,
  History,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronsUpDown,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'motion/react';
import { cn } from '../lib/utils';
import { Logo } from './Logo';
import { useAuth } from '../lib/auth';

const SIDEBAR_EXPANDED = 260;
const SIDEBAR_COLLAPSED = 72;

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
  { icon: Bot, label: 'Agents', path: '/agents' },
  { icon: CreditCard, label: 'Billing', path: '/billing' },
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
        'relative flex h-full flex-col bg-white',
        // card-like vs edge: when used inside DesktopSidebar with padding, this is the card. When standalone (mobile) it's full.
        'overflow-hidden',
        isCompact ? 'border-r border-zinc-200/70' : 'border-r border-zinc-200/60',
        className
      )}
    >
      <div className={cn('flex h-full flex-col', isCompact ? 'px-2 py-4' : 'px-3 py-5')}>
        {/* Brand — inspiration: widelab Team Plan header */}
        <div
          className={cn(
            'flex items-center',
            isCompact ? 'justify-center' : 'justify-between gap-2'
          )}
        >
          <div className={cn('flex items-center min-w-0', isCompact ? 'justify-center' : 'gap-2.5')}>
            <Logo compact={isCompact} />
            {!isCompact && (
              <div className="hidden">
                {/* kept for spacing — logo already contains brand */}
              </div>
            )}
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

        {/* Search */}
        {!isCompact && (
          <div className="relative mt-6">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search"
              className="h-9 w-full rounded-lg border border-zinc-200 bg-[#f8f8f7] pl-9 pr-3 text-[13.5px] font-medium text-zinc-800 placeholder:text-zinc-400 transition-colors focus:border-zinc-200 focus:bg-white focus:outline-none focus:ring-0"
            />
          </div>
        )}
        {isCompact && (
          <div className="mt-5 flex justify-center">
            <button
              type="button"
              className="grid h-9 w-9 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
              aria-label="Search"
              tabIndex={-1}
            >
              <Search className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Primary action */}
        <NavLink
          to="/agents"
          onClick={onClose}
          title={isCompact ? 'New agent' : undefined}
          className={cn(
            'group/nav relative flex items-center text-sm font-medium transition-colors',
            isCompact
              ? 'mx-auto mt-4 h-9 w-9 justify-center rounded-lg bg-black text-white hover:bg-zinc-800'
              : 'mt-4 gap-2 rounded-lg bg-black px-3 py-2.5 text-white hover:bg-zinc-800'
          )}
        >
          <Plus className="h-4 w-4 shrink-0" />
          {!isCompact && <span>New agent</span>}
          <NavTooltip label="New agent" show={isCompact} />
        </NavLink>

        {/* Nav — high contrast like inspiration, dots instead of shortcuts */}
        <nav className={cn('flex-1', isCompact ? 'mt-6 space-y-1' : 'mt-6 space-y-1')}>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              title={isCompact ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  'group/nav relative flex items-center transition-colors',
                  isCompact
                    ? 'mx-auto h-9 w-9 justify-center rounded-lg text-sm'
                    : 'justify-between rounded-lg px-2.5 py-2 text-[14px] font-medium',
                  isActive
                    ? 'bg-[#f3f4f6] text-zinc-900'
                    : 'text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span className={cn('flex items-center', isCompact ? 'justify-center' : 'gap-3 min-w-0')}>
                    <item.icon
                      className={cn(
                        'shrink-0',
                        isCompact ? 'h-[18px] w-[18px]' : 'h-[18px] w-[18px]',
                        isActive ? 'text-zinc-700' : 'text-zinc-500 group-hover/nav:text-zinc-700'
                      )}
                    />
                    {!isCompact && <span className="truncate">{item.label}</span>}
                  </span>
                  {!isCompact && (
                    <span
                      className={cn(
                        'h-1.5 w-1.5 shrink-0 rounded-full transition-colors',
                        isActive ? 'bg-zinc-700' : 'bg-zinc-300 group-hover/nav:bg-zinc-400'
                      )}
                      aria-hidden
                    />
                  )}
                  <NavTooltip label={item.label} show={isCompact} />
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Divider + bottom group like inspiration Settings/Help */}
        <div className={cn('border-t border-zinc-100', isCompact ? 'mt-4 pt-4 space-y-1' : 'mt-4 pt-4 space-y-0.5')}>
          <NavLink
            to="/settings"
            onClick={onClose}
            title={isCompact ? 'Settings' : undefined}
            className={({ isActive }) =>
              cn(
                'group/nav relative flex items-center transition-colors',
                isCompact
                  ? 'mx-auto h-9 w-9 justify-center rounded-lg'
                  : 'justify-between rounded-lg px-2.5 py-2 text-[14px] font-medium',
                isActive
                  ? 'bg-[#f3f4f6] text-zinc-900'
                  : 'text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
              )
            }
          >
            {({ isActive }) => (
              <>
                <span className={cn('flex items-center', isCompact ? 'justify-center' : 'gap-3')}>
                  <Settings className={cn('h-[18px] w-[18px] shrink-0', isActive ? 'text-zinc-600' : 'text-zinc-500 group-hover/nav:text-zinc-600')} />
                  {!isCompact && <span>Settings</span>}
                </span>
                {!isCompact && null}
                <NavTooltip label="Settings" show={isCompact} />
              </>
            )}
          </NavLink>

          <NavLink
            to="/settings"
            onClick={onClose}
            title={isCompact ? 'Help' : undefined}
            className={() =>
              cn(
                'group/nav relative flex items-center transition-colors',
                isCompact
                  ? 'mx-auto h-9 w-9 justify-center rounded-lg text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700'
                  : 'gap-3 rounded-lg px-2.5 py-2 text-[14px] font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
              )
            }
          >
            <HelpCircle className="h-[18px] w-[18px] shrink-0 text-zinc-500 group-hover/nav:text-zinc-600" />
            {!isCompact && <span>Help</span>}
            <NavTooltip label="Help" show={isCompact} />
          </NavLink>

          <button
            type="button"
            onClick={() => {
              signOut();
              onClose?.();
            }}
            title={isCompact ? 'Sign out' : undefined}
            className={cn(
              'group/nav relative flex w-full items-center transition-colors',
              isCompact
                ? 'mx-auto h-9 w-9 justify-center rounded-lg text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700'
                : 'gap-3 rounded-lg px-2.5 py-2 text-[14px] font-medium text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900'
            )}
          >
            <LogOut className="h-[18px] w-[18px] shrink-0 text-zinc-500 group-hover/nav:text-zinc-600" />
            {!isCompact && <span>Sign out</span>}
            <NavTooltip label="Sign out" show={isCompact} />
          </button>
        </div>

        {/* User — inspiration: Sandra Marx card */}
        <div
          className={cn(
            'flex items-center border-t border-zinc-100',
            isCompact ? 'mx-auto mt-4 h-9 w-9 justify-center border-0 pt-0' : 'mt-3 gap-3 px-1.5 py-3'
          )}
          title={isCompact ? user?.email : undefined}
        >
          <div className="grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-lg bg-zinc-100 ring-1 ring-zinc-200">
            {/* use initials as fallback, but rounded-lg like inspiration avatar */}
            <span className="grid h-full w-full place-items-center bg-zinc-900 text-[11px] font-semibold text-white">
              {userInitials(user?.email)}
            </span>
          </div>
          {!isCompact && (
            <>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-semibold leading-none text-zinc-900">
                  {user?.email?.split('@')[0] ?? 'Account'}
                </p>
                <p className="truncate text-xs leading-none text-zinc-500 mt-1">{user?.email ?? '—'}</p>
              </div>
              <ChevronsUpDown className="h-4 w-4 shrink-0 text-zinc-400" />
            </>
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
      className="fixed left-0 top-0 z-50 hidden h-full p-3 md:block"
    >
      <div className="h-full overflow-hidden rounded-xl border border-zinc-200/60 bg-white shadow-sm">
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

export function TopAppBar({ onMenuClick }: TopAppBarProps) {
  const location = useLocation();
  const { user } = useAuth();
  const searchPlaceholder = location.pathname.includes('agents')
    ? 'Search agents...'
    : 'Search workspace...';

  const isDeployRoute = location.pathname.includes('/deploy');

  const pageTitle = (() => {
    if (location.pathname.includes('/deploy/widget')) return 'Chat widget';
    if (location.pathname.includes('/deploy/help-page')) return 'Help page';
    if (location.pathname.match(/\/deploy\/(email|whatsapp|phone)$/)) {
      const channel = location.pathname.split('/').pop();
      return channel ? channel.charAt(0).toUpperCase() + channel.slice(1) : 'Deploy';
    }
    if (location.pathname.includes('/deploy')) return 'Deploy';
    if (location.pathname.startsWith('/guides')) return 'Guides';
    if (location.pathname.startsWith('/agents')) return 'Agents';
    if (location.pathname.startsWith('/dashboard')) return 'Dashboard';
    if (location.pathname.startsWith('/billing')) return 'Usage';
    if (location.pathname.startsWith('/settings')) return 'Settings';
    return 'Workspace';
  })();

  return (
    <header
      className={cn(
        'sticky top-0 z-40 flex w-full items-center justify-between gap-3 border-b border-zinc-200/70 bg-white/80 px-3 backdrop-blur-md md:px-5',
        isDeployRoute ? 'h-12' : 'h-14 gap-4 md:h-16 md:px-6'
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="grid h-9 w-9 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        {!isDeployRoute && (
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-semibold text-zinc-900">{pageTitle}</p>
            <p className="truncate text-[11px] text-zinc-500">HelpDeskAI workspace</p>
          </div>
        )}

        <div
          className={cn(
            'relative hidden max-w-sm flex-1 sm:block lg:max-w-md',
            isDeployRoute ? 'ml-0' : 'ml-auto sm:ml-0'
          )}
        >
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            className="h-9 w-full rounded-lg border border-zinc-200 bg-zinc-50 pl-9 pr-3 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors focus:border-zinc-300 focus:bg-white focus:outline-none"
          />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1.5 md:gap-2">
        <button
          type="button"
          className="grid h-9 w-9 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900"
          aria-label="Notifications"
        >
          <Bell className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          className="hidden h-9 w-9 place-items-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 sm:grid"
          aria-label="History"
        >
          <History className="h-[18px] w-[18px]" />
        </button>
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
