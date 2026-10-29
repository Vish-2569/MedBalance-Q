import { useQuery } from '@tanstack/react-query';
import {
  Trophy, TrendingDown, Package, Truck, ShieldCheck,
  AlertTriangle, BarChart3, Loader2,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '@/lib/api';
import { cn, formatPct, formatINR } from '@/lib/utils';

const COLORS = ['#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

export default function ResultsPage() {
  const { data: metrics, isLoading, error } = useQuery({ queryKey: ['resultMetrics'], queryFn: api.getResultMetrics });
  const { data: planDemo } = useQuery({ queryKey: ['plan'], queryFn: api.getPlanDemo });
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => api.getPositions() });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (error || !metrics) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
        <Trophy className="w-10 h-10" />
        <p className="text-sm">Run a plan to see results</p>
      </div>
    );
  }

  const orders = planDemo?.orders ?? [];
  const byDrug = orders.reduce<Record<string, number>>((acc, o) => {
    acc[o.drug_name] = (acc[o.drug_name] ?? 0) + o.qty;
    return acc;
  }, {});
  const chartData = Object.entries(byDrug).map(([name, qty]) => ({ name: name.split(' ')[0], qty }));

  const shortageData = positions
    .filter(p => p.shortage > 0)
    .map(p => ({ name: `${p.facility_id}-${p.drug_code}`, shortage: p.shortage }));

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">Results Dashboard</h1>
        <span className="text-xs px-3 py-1 rounded-full bg-teal-50 text-teal-700 font-medium flex items-center gap-1">
          <ShieldCheck className="w-3 h-3" />
          {formatPct(metrics.shortage_reduction)} shortage reduced
        </span>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard
          icon={TrendingDown}
          label="Stockout Days Saved"
          value={String(metrics.stockout_days_before - metrics.stockout_days_after)}
          sub={`${metrics.stockout_days_before} → ${metrics.stockout_days_after}`}
          color="text-teal-600"
        />
        <MetricCard
          icon={Package}
          label="Expiry Value Saved"
          value={formatINR(metrics.expired_value_avoided_inr)}
          sub={`of ${formatINR(metrics.expired_value_inr)} at risk`}
          color="text-amber-600"
        />
        <MetricCard
          icon={Truck}
          label="Waste Moved"
          value={`${metrics.waste_moved_units} units`}
          sub={formatPct(metrics.waste_moved_pct)}
          color="text-blue-600"
        />
        <MetricCard
          icon={Trophy}
          label="Shortage Reduction"
          value={formatPct(metrics.shortage_reduction)}
          sub={`CI: ${formatPct(metrics.ci_lower)} – ${formatPct(metrics.ci_upper)}`}
          color="text-teal-600"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">Units Transferred by Drug</h3>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="qty" fill="#14b8a6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <ChartPlaceholder label="No transfer data yet" />
          )}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">Remaining Shortages</h3>
          {shortageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={shortageData} dataKey="shortage" nameKey="name" cx="50%" cy="50%"
                  outerRadius={80} label={({ name }) => name}>
                  {shortageData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <ChartPlaceholder label="No shortages remaining" />
          )}
        </div>
      </div>

      {/* Stockout reduction bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-600 mb-3 flex items-center gap-2">
          <BarChart3 className="w-4 h-4" /> Stockout Reduction
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
              <span>Before: {metrics.stockout_days_before} facility-drug-days</span>
              <span>After: {metrics.stockout_days_after}</span>
            </div>
            <div className="h-6 bg-red-100 rounded-full overflow-hidden relative">
              <div
                className="h-full bg-teal-500 rounded-full transition-all"
                style={{ width: `${((metrics.stockout_days_before - metrics.stockout_days_after) / Math.max(metrics.stockout_days_before, 1)) * 100}%` }}
              />
            </div>
          </div>
          <span className="text-lg font-bold text-teal-600 w-16 text-right">
            {Math.round(((metrics.stockout_days_before - metrics.stockout_days_after) / Math.max(metrics.stockout_days_before, 1)) * 100)}%
          </span>
        </div>
      </div>

      {/* Ablation table */}
      {metrics.ablation.length > 0 && (
        <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-semibold text-slate-700">Policy Ablation Study</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
                  <th className="text-left px-4 py-2.5 font-medium">Variant</th>
                  <th className="text-right px-4 py-2.5 font-medium">Shortage Red.</th>
                  <th className="text-right px-4 py-2.5 font-medium">Expiry Avoided</th>
                  <th className="text-right px-4 py-2.5 font-medium">Cost</th>
                  <th className="text-left px-4 py-2.5 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {metrics.ablation.map((row, i) => (
                  <tr key={row.variant} className={cn(
                    'border-t border-slate-100',
                    i === 0 && 'bg-teal-50/50',
                  )}>
                    <td className="px-4 py-2.5 font-medium text-slate-800">
                      <span className="flex items-center gap-2">
                        {i === 0 && <Trophy className="w-3.5 h-3.5 text-teal-600" />}
                        {row.variant}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className={cn('h-full rounded-full', i === 0 ? 'bg-teal-500' : 'bg-slate-400')}
                            style={{ width: `${row.shortage_reduction * 100}%` }}
                          />
                        </div>
                        <span className="font-mono w-12 text-right">{formatPct(row.shortage_reduction)}</span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono">{row.expiry_avoided} units</td>
                    <td className="px-4 py-2.5 text-right font-mono">{formatINR(row.cost_inr)}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, sub, color }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className={cn('text-lg font-bold', color ?? 'text-slate-800')}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function ChartPlaceholder({ label }: { label: string }) {
  return (
    <div className="h-[220px] flex items-center justify-center text-slate-400 text-sm">
      {label}
    </div>
  );
}
