import { ReactNode, useState } from 'react';
import { Sidebar, TopAppBar } from './Navigation';
import { motion, AnimatePresence } from 'motion/react';
import { useLocation } from 'react-router-dom';
import { X } from 'lucide-react';

export function AppLayout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-surface">
      {/* Desktop Sidebar */}
      <Sidebar className="hidden md:flex fixed left-0 top-0 h-full w-64" />

      {/* Mobile Drawer */}
      <AnimatePresence>
        {isSidebarOpen && (
          <>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 bg-zinc-950/40 backdrop-blur-sm z-[60] md:hidden"
            />
            <motion.div 
              initial={{ x: -256 }}
              animate={{ x: 0 }}
              exit={{ x: -256 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed left-0 top-0 bottom-0 w-64 bg-surface-container-lowest z-[70] md:hidden shadow-2xl"
            >
              <div className="absolute right-4 top-4">
                <button onClick={() => setSidebarOpen(false)} className="p-2 text-on-surface-variant hover:text-brand-primary">
                  <X className="w-6 h-6" />
                </button>
              </div>
              <Sidebar onClose={() => setSidebarOpen(false)} className="w-full border-none" />
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <div className="flex-1 md:ml-64 flex flex-col min-w-0">
        <TopAppBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 p-4 md:p-8 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="max-w-[1440px] mx-auto"
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
