import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import {
  LayoutDashboard, Users, Shield, AlertTriangle, CreditCard,
  Briefcase, FileText, BarChart3, LogOut, Globe, ChevronLeft, ChevronRight, Menu, BookOpen,
  Search, ClipboardCheck, Brain, ShieldCheck, FileCheck, Target, PieChart,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

const navItems = [
  { key: 'nav.dashboard', path: '/', icon: LayoutDashboard },
  { key: 'nav.onboarding', path: '/onboarding', icon: Users },
  { key: 'nav.screening', path: '/screening', icon: Shield },
  { key: 'nav.risk', path: '/risk', icon: AlertTriangle },
  { key: 'nav.transactions', path: '/transactions', icon: CreditCard },
  { key: 'nav.cases', path: '/cases', icon: Briefcase },
  { key: 'nav.audit', path: '/audit', icon: FileText },
  { key: 'nav.analytics', path: '/analytics', icon: BarChart3 },
  { key: 'nav.compliance', path: '/compliance', icon: BookOpen },
  { key: 'nav.reg_search', path: '/reg-search', icon: Search },
  { key: 'nav.review_queue', path: '/review-queue', icon: ClipboardCheck },
  { key: 'nav.intelligence', path: '/intelligence', icon: Brain },
  { key: 'nav.controls', path: '/controls', icon: ShieldCheck },
  { key: 'nav.evidence', path: '/evidence', icon: FileCheck },
  { key: 'nav.gap_analysis', path: '/gap-analysis', icon: Target },
  { key: 'nav.exec_report', path: '/executive-report', icon: PieChart },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-slate-50" dir={language === 'ar' ? 'rtl' : 'ltr'}>
      {/* Sidebar */}
      <aside className={`${collapsed ? 'w-16' : 'w-64'} bg-slate-900 text-white flex flex-col transition-all duration-200`}>
        <div className="p-4 border-b border-slate-700 flex items-center justify-between">
          {!collapsed && (
            <div>
              <h1 className="font-bold text-lg">AML-OS</h1>
              <p className="text-xs text-slate-400">{t('app.subtitle')}</p>
            </div>
          )}
          <Button variant="ghost" size="icon" onClick={() => setCollapsed(!collapsed)} className="text-white hover:bg-slate-800">
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </Button>
        </div>

        <nav className="flex-1 py-4 space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
                title={collapsed ? t(item.key) : undefined}
              >
                <Icon size={20} />
                {!collapsed && <span className="text-sm">{t(item.key)}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-700 space-y-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setLanguage(language === 'en' ? 'ar' : 'en')}
            className="w-full justify-start text-slate-300 hover:text-white hover:bg-slate-800"
          >
            <Globe size={16} className="me-2" />
            {!collapsed && (language === 'en' ? 'العربية' : 'English')}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="w-full justify-start text-slate-300 hover:text-white hover:bg-slate-800"
          >
            <LogOut size={16} className="me-2" />
            {!collapsed && t('nav.logout')}
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setCollapsed(!collapsed)}>
              <Menu size={20} />
            </Button>
            <h2 className="text-lg font-semibold text-slate-800">
              {navItems.find(n => n.path === location.pathname || (n.path !== '/' && location.pathname.startsWith(n.path)))
                ? t(navItems.find(n => n.path === location.pathname || (n.path !== '/' && location.pathname.startsWith(n.path)))!.key)
                : t('nav.dashboard')}
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-800">{user?.full_name}</p>
              <p className="text-xs text-slate-500 capitalize">{user?.role?.replace('_', ' ')}</p>
            </div>
            <div className="h-9 w-9 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-medium">
              {user?.full_name?.charAt(0)}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
