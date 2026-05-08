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
  X
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '../lib/utils';
import { Logo } from './Logo';
import { useAuth } from '../lib/auth';

export function Sidebar({ className, onClose }: { className?: string, onClose?: () => void }) {
  const { signOut } = useAuth();
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
    { icon: Bot, label: 'Agents', path: '/agents' },
    { icon: CreditCard, label: 'Billing', path: '/billing' },
    { icon: Settings, label: 'Settings', path: '/settings' },
  ];

  return (
    <aside className={cn("h-full w-64 border-r border-surface-container-highest bg-surface-container-lowest flex flex-col p-4", className)}>
      <div className="mb-8 px-2">
        <Logo />
        <div className="text-[10px] ml-11 font-semibold text-on-surface-variant uppercase tracking-widest opacity-60">Precision Support</div>
      </div>

      <NavLink to="/agents" onClick={onClose} className="mb-6 w-full py-2 px-4 bg-brand-primary text-brand-on-primary rounded-default hover:opacity-90 transition-opacity flex items-center justify-center gap-2 font-medium text-sm">
        <Plus className="w-4 h-4" />
        New Agent
      </NavLink>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onClose}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-4 py-2 rounded-default transition-all duration-200 text-sm font-medium",
              isActive 
                ? "bg-brand-primary text-brand-on-primary shadow-sm" 
                : "text-on-surface-variant hover:text-brand-primary hover:bg-surface-container-low"
            )}
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto pt-4 border-t border-surface-container-highest space-y-1">
        <NavLink
          to="/settings"
          onClick={onClose}
          className="flex items-center gap-3 px-4 py-2 rounded-default transition-all duration-200 text-sm font-medium text-on-surface-variant hover:text-brand-primary hover:bg-surface-container-low"
        >
          <HelpCircle className="w-5 h-5" />
          Support
        </NavLink>
        <button
          onClick={() => {
            signOut();
            onClose?.();
          }}
          className="w-full flex items-center gap-3 px-4 py-2 rounded-default transition-all duration-200 text-sm font-medium text-on-surface-variant hover:text-brand-primary hover:bg-surface-container-low"
        >
          <LogOut className="w-5 h-5" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}

export function TopAppBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const location = useLocation();
  const searchPlaceholder = location.pathname.includes('agents') ? 'SEARCH AGENTS...' : 'SEARCH WORKSPACE...';

  return (
    <header className="sticky top-0 z-40 h-16 w-full border-b border-surface-container-highest bg-surface-container-lowest/80 backdrop-blur-md flex items-center justify-between px-4 md:px-8">
      <div className="flex items-center gap-4">
        <button 
          onClick={onMenuClick}
          className="md:hidden p-2 text-on-surface-variant hover:text-brand-primary transition-colors"
        >
          <Menu className="w-6 h-6" />
        </button>
        <div className="flex-1 max-w-md relative focus-within:ring-1 focus-within:ring-brand-primary rounded-default hidden sm:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-on-surface-variant opacity-40" />
          <input 
            type="text" 
            placeholder={searchPlaceholder}
            className="w-full bg-transparent border-none pl-10 py-2 text-xs font-semibold uppercase tracking-widest focus:ring-0 placeholder:text-on-surface-variant/40"
          />
        </div>
      </div>

      <div className="flex items-center gap-3 md:gap-6">
        <button className="text-on-surface-variant hover:text-brand-primary transition-colors">
          <Bell className="w-5 h-5" />
        </button>
        <button className="hidden sm:block text-on-surface-variant hover:text-brand-primary transition-colors">
          <History className="w-5 h-5" />
        </button>
        <div className="w-8 h-8 rounded-full bg-surface-container-high border border-surface-container-highest overflow-hidden cursor-pointer hover:border-brand-primary transition-colors">
          <img 
            src="https://lh3.googleusercontent.com/aida-public/AB6AXuA3VG2-O6nWGXk1sK2huEmFEQzFLEXK9hlE2Y1ZtGpu6DvkPkb7qMw2fC-CrCz1NHpcCjglrskKuUJC-xbZVjYJXA0W-i1xXhYmfNlD11UTqI3EvH-4BxC_hw7cQ3Y13_AS5Oev9RNiyB7Qe3DdZ5a6qrD7pezyTrWNe6kjumxz-i7wWQW5Tx6t3W685L1iozIBuQKT98GRLONAd5PoUfVR3OBNgKlJz1PcUgccFqwqCP9pAs4XrPNxoftgmZG-9t8QO6A9US07aR7d" 
            alt="User profile"
            className="w-full h-full object-cover grayscale"
          />
        </div>
      </div>
    </header>
  );
}
