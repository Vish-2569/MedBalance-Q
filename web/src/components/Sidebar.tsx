import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Map, FileInput, ClipboardList, BarChart3,
  Thermometer, Trophy, Brain, Beaker,
  ChevronLeft, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLiveEvents } from '@/hooks/useSSE';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

const NAV = [
  { to: '/', icon: Map, label: 'Dashboard' },
  { to: '/ingestion', icon: FileInput, label: 'Ingestion', badgeKey: 'reviews' as const },
  { to: '/plan', icon: ClipboardList, label: 'Plan' },
  { to: '/benchmark', icon: BarChart3, label: 'Benchmark' },
  { to: '/coldchain', icon: Thermometer, label: 'Cold Chain', badgeKey: 'coldchain' as const },
  { to: '/results', icon: Trophy, label: 'Results' },
  { to: '/ai-health', icon: Brain, label: 'AI Health' },
  { to: '/scenarios', icon: Beaker, label: 'Scenarios' },
] as const;

function useIsNarrow(breakpoint = 1400) {
  const [narrow, setNarrow] = useState(
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false,
  );
  useEffect(() => {
    const handler = () => setNarrow(window.innerWidth < breakpoint);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [breakpoint]);
  return narrow;
}

export default function Sidebar() {
  const isNarrow = useIsNarrow();
  const [collapsed, setCollapsed] = useState(isNarrow);

  useEffect(() => { setCollapsed(isNarrow); }, [isNarrow]);

  const { data: reviews = [] } = useQuery({ queryKey: ['reviews'], queryFn: api.getReviews });
  const events = useLiveEvents(50);

  const pendingReviews = reviews.filter(r => r.status === 'pending').length;
  const coldchainAlerts = events.filter(e => e.type === 'coldchain.alert').length;

  const badges: Record<string, number> = {
    reviews: pendingReviews,
    coldchain: coldchainAlerts,
  };

  return (
    <nav className={cn(
      'sidebar-nav bg-white border-r border-slate-200 flex flex-col py-3 shrink-0 transition-all duration-200',
      collapsed ? 'w-14' : 'w-52',
    )}>
      {NAV.map(({ to, icon: Icon, label, ...rest }) => {
        const badgeCount = 'badgeKey' in rest ? badges[rest.badgeKey] ?? 0 : 0;
        return (
          <NavLink
            key={to}
            to={to}
            title={label}
            className={({ isActive }) => cn(
              'relative flex items-center text-sm font-medium transition-colors mx-2 rounded-lg',
              collapsed ? 'justify-center px-2 py-2.5' : 'gap-3 px-4 py-2.5',
              isActive
                ? 'bg-teal-50 text-teal-700'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50',
            )}
          >
            <Icon className="w-4 h-4 shrink-0" />
            {!collapsed && <span className="nav-label flex-1">{label}</span>}
            {!collapsed && badgeCount > 0 && (
              <span className="nav-badge min-w-5 h-5 flex items-center justify-center rounded-full bg-red-500 text-white text-xs font-bold px-1">
                {badgeCount}
              </span>
            )}
            {collapsed && badgeCount > 0 && (
              <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500" />
            )}
          </NavLink>
        );
      })}

      <div className="flex-1" />

      <button
        onClick={() => setCollapsed(c => !c)}
        className="mx-2 p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors flex items-center justify-center"
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </nav>
  );
}
