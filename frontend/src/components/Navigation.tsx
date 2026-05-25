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
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
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
        'pointer-events-none absolute left-[calc(100%+10px)] top-1/2 z-[100] -translate-y-1/2',
        'whitespace-nowrap rounded-lg border border-surface-container-highest bg-brand-primary px-2.5 py-1.5',
        'text-xs font-semibold text-brand-on-primary shadow-lg',
        'opacity-0 scale-95 transition-all duration-150',
        'group-hover/nav:opacity-100 group-hover/nav:scale-100',
        'group-focus-within/nav:opacity-100 group-focus-within/nav:scale-100'
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
        'relative flex h-full flex-col overflow-hidden',
        'border-r border-surface-container-highest/80 bg-surface-container-lowest',
        className
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(0,0,0,0.03),transparent_55%)]"
        aria-hidden
      />

      <div className={cn('relative flex flex-col h-full', isCompact ? 'px-2.5 py-4' : 'px-3 py-5')}>
        {/* Brand */}
        <div
          className={cn(
            'flex items-center',
            isCompact ? 'justify-center' : 'justify-between gap-2 px-1'
          )}
        >
          <Logo compact={isCompact} />
          {showCollapseControl && onToggleCollapsed && !isCompact && (
            <button
              type="button"
              onClick={onToggleCollapsed}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant transition-colors hover:border-brand-primary/30 hover:bg-surface-container-low hover:text-brand-primary"
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
            className="mx-auto mt-4 grid h-9 w-9 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant transition-colors hover:border-brand-primary/30 hover:bg-surface-container-low hover:text-brand-primary"
            aria-label="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        )}

        {/* New agent */}
        <NavLink
          to="/agents"
          onClick={onClose}
          title={isCompact ? 'New agent' : undefined}
          className={cn(
            'group/nav relative mt-6 flex items-center font-semibold transition-all duration-200',
            'bg-brand-primary text-brand-on-primary shadow-sm hover:opacity-90',
            isCompact
              ? 'mx-auto h-10 w-10 justify-center rounded-xl'
              : 'gap-2.5 rounded-xl px-3.5 py-2.5 text-sm'
          )}
        >
          <Plus className={cn('shrink-0', isCompact ? 'h-5 w-5' : 'h-4 w-4')} />
          {!isCompact && <span>New agent</span>}
          <NavTooltip label="New agent" show={isCompact} />
        </NavLink>

        {/* Main nav */}
        <nav className={cn('mt-6 flex-1 space-y-1', isCompact && 'space-y-1.5')}>
          {!isCompact && (
            <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-on-surface-variant/50">
              Workspace
            </p>
          )}
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              title={isCompact ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  'group/nav relative flex items-center transition-all duration-200',
                  isCompact
                    ? 'mx-auto h-10 w-10 justify-center rounded-xl'
                    : 'gap-3 rounded-xl px-3 py-2.5 text-sm font-medium',
                  isActive
                    ? isCompact
                      ? 'bg-brand-primary text-brand-on-primary shadow-md'
                      : 'bg-brand-primary text-brand-on-primary shadow-sm'
                    : 'text-on-surface-variant hover:bg-surface-container-low hover:text-brand-primary'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn(
                      'shrink-0',
                      isCompact ? 'h-5 w-5' : 'h-[18px] w-[18px]',
                      isActive && !isCompact && 'opacity-100'
                    )}
                  />
                  {!isCompact && <span className="truncate">{item.label}</span>}
                  {isActive && !isCompact && (
                    <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-brand-on-primary/80" />
                  )}
                  <NavTooltip label={item.label} show={isCompact} />
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Upgrade hint — expanded only */}
        {!isCompact && (
          <div className="mt-4 rounded-xl border border-surface-container-highest bg-surface-container-low p-3.5">
            <div className="flex items-start gap-2.5">
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-primary/5 text-brand-primary">
                <Sparkles className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-xs font-bold text-brand-primary">Full access</p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-on-surface-variant">
                  All agents and channels unlocked.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div
          className={cn(
            'mt-4 border-t border-surface-container-highest pt-4 space-y-1',
            isCompact && 'space-y-1.5'
          )}
        >
          <NavLink
            to="/settings"
            onClick={onClose}
            title={isCompact ? 'Support' : undefined}
            className={({ isActive }) =>
              cn(
                'group/nav relative flex items-center text-sm font-medium transition-colors duration-200',
                isCompact
                  ? 'mx-auto h-10 w-10 justify-center rounded-xl'
                  : 'gap-3 rounded-xl px-3 py-2.5',
                isActive
                  ? 'bg-surface-container-low text-brand-primary'
                  : 'text-on-surface-variant hover:bg-surface-container-low hover:text-brand-primary'
              )
            }
          >
            <HelpCircle className={cn('shrink-0', isCompact ? 'h-5 w-5' : 'h-[18px] w-[18px]')} />
            {!isCompact && <span>Support</span>}
            <NavTooltip label="Support" show={isCompact} />
          </NavLink>

          <button
            type="button"
            onClick={() => {
              signOut();
              onClose?.();
            }}
            title={isCompact ? 'Sign out' : undefined}
            className={cn(
              'group/nav relative flex w-full items-center text-sm font-medium text-on-surface-variant transition-colors duration-200 hover:bg-rose-50 hover:text-rose-700',
              isCompact
                ? 'mx-auto h-10 w-10 justify-center rounded-xl'
                : 'gap-3 rounded-xl px-3 py-2.5'
            )}
          >
            <LogOut className={cn('shrink-0', isCompact ? 'h-5 w-5' : 'h-[18px] w-[18px]')} />
            {!isCompact && <span>Sign out</span>}
            <NavTooltip label="Sign out" show={isCompact} />
          </button>

          {/* User */}
          <div
            className={cn(
              'flex items-center rounded-xl border border-surface-container-highest bg-surface',
              isCompact ? 'mx-auto mt-2 h-10 w-10 justify-center' : 'mt-2 gap-3 p-2.5'
            )}
            title={isCompact ? user?.email : undefined}
          >
            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-primary text-xs font-bold text-brand-on-primary">
              {userInitials(user?.email)}
            </div>
            {!isCompact && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-bold text-brand-primary">
                  {user?.email?.split('@')[0] ?? 'Account'}
                </p>
                <p className="truncate text-[10px] text-on-surface-variant">{user?.email}</p>
              </div>
            )}
          </div>
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
      <Sidebar
        collapsed={collapsed}
        onToggleCollapsed={onToggleCollapsed}
        className="h-full w-full"
      />
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
        'sticky top-0 z-40 flex w-full items-center justify-between gap-3 border-b border-surface-container-highest/80 bg-surface-container-lowest/90 px-3 backdrop-blur-md md:px-5',
        isDeployRoute ? 'h-12' : 'h-14 gap-4 md:h-16 md:px-6'
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <button
          type="button"
          onClick={onMenuClick}
          className="grid h-9 w-9 place-items-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-brand-primary md:hidden"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        {!isDeployRoute && (
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-bold text-brand-primary">{pageTitle}</p>
            <p className="truncate text-[11px] text-on-surface-variant">HelpDeskAI workspace</p>
          </div>
        )}

        <div
          className={cn(
            'relative hidden max-w-sm flex-1 sm:block lg:max-w-md',
            isDeployRoute ? 'ml-0' : 'ml-auto sm:ml-0'
          )}
        >
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-on-surface-variant/40" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            className="h-9 w-full rounded-lg border border-transparent bg-surface-container-low pl-9 pr-3 text-sm text-brand-primary placeholder:text-on-surface-variant/50 transition-colors focus:border-surface-container-highest focus:bg-surface-container-lowest focus:outline-none focus:ring-1 focus:ring-brand-primary/20"
          />
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-1.5 md:gap-2">
        <button
          type="button"
          className="grid h-9 w-9 place-items-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-brand-primary"
          aria-label="Notifications"
        >
          <Bell className="h-[18px] w-[18px]" />
        </button>
        <button
          type="button"
          className="hidden h-9 w-9 place-items-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-brand-primary sm:grid"
          aria-label="History"
        >
          <History className="h-[18px] w-[18px]" />
        </button>
        <div
          className="grid h-9 w-9 place-items-center rounded-lg border border-surface-container-highest bg-brand-primary text-xs font-bold text-brand-on-primary"
          title={user?.email}
        >
          {userInitials(user?.email)}
        </div>
      </div>
    </header>
  );
}
