import { ReactNode, useCallback, useEffect, useState } from 'react';
import {
  DesktopSidebar,
  Sidebar,
  TopAppBar,
  SIDEBAR_COLLAPSED,
  SIDEBAR_EXPANDED,
} from './Navigation';
import { motion, AnimatePresence } from 'motion/react';
import { useLocation } from 'react-router-dom';
import { X } from 'lucide-react';

const SIDEBAR_STORAGE_KEY = 'helpdeskai.sidebar_collapsed';

export function AppLayout({
  children,
  compact = false,
}: {
  children: ReactNode;
  compact?: boolean;
}) {
  const location = useLocation();
  const [isMobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true';
  });

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const sidebarWidth = collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED;

  return (
    <div className="flex min-h-screen bg-surface">
      <DesktopSidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />

      <AnimatePresence>
        {isMobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setMobileOpen(false)}
              className="fixed inset-0 z-[60] bg-zinc-950/50 backdrop-blur-sm md:hidden"
            />
            <motion.div
              initial={{ x: -SIDEBAR_EXPANDED }}
              animate={{ x: 0 }}
              exit={{ x: -SIDEBAR_EXPANDED }}
              transition={{ type: 'spring', damping: 28, stiffness: 320 }}
              className="fixed left-0 top-0 bottom-0 z-[70] w-[260px] shadow-2xl md:hidden"
            >
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="absolute right-3 top-4 z-10 grid h-9 w-9 place-items-center rounded-lg border border-surface-container-highest bg-surface text-on-surface-variant hover:text-brand-primary"
                aria-label="Close menu"
              >
                <X className="h-5 w-5" />
              </button>
              <Sidebar
                onClose={() => setMobileOpen(false)}
                showCollapseControl={false}
                className="h-full w-full"
              />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <motion.div
        initial={false}
        animate={{ marginLeft: sidebarWidth }}
        transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
        className="flex min-w-0 flex-1 flex-col max-md:!ml-0"
      >
        <TopAppBar onMenuClick={() => setMobileOpen(true)} />
        <main
          className={
            compact
              ? 'flex-1 overflow-y-auto px-3 py-3 md:px-5 md:py-4'
              : 'flex-1 overflow-y-auto p-4 md:p-8'
          }
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: compact ? 4 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: compact ? 0 : -8 }}
              transition={{ duration: compact ? 0.18 : 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="mx-auto max-w-[1440px]"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </motion.div>
    </div>
  );
}
