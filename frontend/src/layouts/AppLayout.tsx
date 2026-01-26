import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  Calendar,
  Upload,
  Settings2,
  Play,
  FileText,
  History,
  Menu,
  X,
  Home,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useUIStore } from '@/stores';
import { TooltipProvider } from '@/components/ui/tooltip';

const navigation = [
  { name: 'Home', href: '/', icon: Home },
  { name: 'Upload Data', href: '/upload', icon: Upload },
  { name: 'Constraints', href: '/constraints', icon: Settings2 },
  { name: 'Generate', href: '/generate', icon: Play },
  { name: 'Recent Jobs', href: '/jobs', icon: History },
];

export function AppLayout() {
  const location = useLocation();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        {/* Mobile header */}
        <header className="lg:hidden fixed top-0 left-0 right-0 z-50 flex h-16 items-center gap-4 border-b bg-background px-4">
          <Button variant="ghost" size="icon" onClick={toggleSidebar} aria-label="Toggle menu">
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
          <div className="flex items-center gap-2">
            <Calendar className="h-6 w-6 text-primary" />
            <span className="font-semibold">Timetable Generator</span>
          </div>
        </header>

        {/* Sidebar */}
        <aside
          className={cn(
            'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card transition-transform duration-200 ease-in-out',
            'lg:translate-x-0',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full'
          )}
        >
          {/* Logo */}
          <div className="flex h-16 items-center gap-2 border-b px-6">
            <Calendar className="h-6 w-6 text-primary" />
            <span className="font-semibold">Timetable Generator</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-4">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href;
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                  onClick={() => {
                    if (window.innerWidth < 1024) {
                      toggleSidebar();
                    }
                  }}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </NavLink>
              );
            })}
          </nav>

          {/* Footer */}
          <div className="border-t p-4">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <FileText className="h-4 w-4" />
              <span>v1.0.0</span>
            </div>
          </div>
        </aside>

        {/* Backdrop for mobile */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
            onClick={toggleSidebar}
            aria-hidden="true"
          />
        )}

        {/* Main content */}
        <main className={cn('min-h-screen transition-all duration-200', 'lg:pl-64', 'pt-16 lg:pt-0')}>
          <div className="container mx-auto p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </TooltipProvider>
  );
}
