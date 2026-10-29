import type { Position, Facility } from '@/types/domain';

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function venColor(ven: string): string {
  if (ven === 'V') return 'text-red-600';
  if (ven === 'E') return 'text-amber-600';
  return 'text-slate-500';
}

export function venBg(ven: string): string {
  if (ven === 'V') return 'bg-red-50 border-red-200';
  if (ven === 'E') return 'bg-amber-50 border-amber-200';
  return 'bg-slate-50 border-slate-200';
}

export function statusColor(status: string): string {
  switch (status) {
    case 'proposed': return 'bg-slate-100 text-slate-700';
    case 'approved': return 'bg-teal-100 text-teal-700';
    case 'dispatched': case 'in_transit': return 'bg-blue-100 text-blue-700';
    case 'delivered': return 'bg-green-100 text-green-700';
    case 'rejected': case 'cancelled': return 'bg-red-100 text-red-700';
    default: return 'bg-slate-100 text-slate-600';
  }
}

export function stockHealthColor(positions: Position[]): string {
  if (positions.length === 0) return '#94a3b8';
  const totalShortage = positions.reduce((s, p) => s + p.shortage, 0);
  const totalTarget = positions.reduce((s, p) => s + (p.consumption_rate * p.target_days), 0);
  if (totalTarget === 0) return '#14b8a6';
  const ratio = totalShortage / totalTarget;
  if (ratio > 0.5) return '#ef4444';
  if (ratio > 0.2) return '#f59e0b';
  return '#14b8a6';
}

export function facilityLabel(f: Facility): string {
  return f.name.replace('SIM-', '');
}

export function formatINR(n: number): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);
}

export function formatPct(n: number): string {
  return `${(n * 100).toFixed(0)}%`;
}

export function daysUntil(dateStr: string, fromStr?: string): number {
  const from = fromStr ? new Date(fromStr) : new Date();
  const to = new Date(dateStr);
  return Math.ceil((to.getTime() - from.getTime()) / 86_400_000);
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
