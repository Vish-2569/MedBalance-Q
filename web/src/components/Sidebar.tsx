import { NavLink } from 'react-router-dom';
import {
  Map, FileInput, ClipboardList, BarChart3,
  Thermometer, Trophy, Brain, Beaker,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV = [
  { to: '/', icon: Map, label: 'Map' },
  { to: '/ingestion', icon: FileInput, label: 'Ingestion' },
  { to: '/plan', icon: ClipboardList, label: 'Plan' },
  { to: '/benchmark', icon: BarChart3, label: 'Benchmark' },
  { to: '/coldchain', icon: Thermometer, label: 'Cold Chain' },
  { to: '/results', icon: Trophy, label: 'Results' },
  { to: '/ai-health', icon: Brain, label: 'AI Health' },
  { to: '/scenarios', icon: Beaker, label: 'Scenarios' },
] as const;

export default function Sidebar() {
  return (
    <nav className="w-52 bg-white border-r border-slate-200 flex flex-col py-3 shrink-0">
      {NAV.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) => cn(
            'flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors mx-2 rounded-lg',
            isActive
              ? 'bg-teal-50 text-teal-700'
              : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50',
          )}
        >
          <Icon className="w-4 h-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
