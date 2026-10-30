import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { Loader2, Award, Zap, GitCompare } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatPct } from '@/lib/utils';
import type { Benchmark } from '@/types/domain';

const SOLVER_COLORS: Record<string, string> = {
  'no-transfer': '#94a3b8',
  'greedy-phone-call': '#f59e0b',
  'greedy-f4': '#3b82f6',
  'qubo (greedy-descent)': '#8b5cf6',
  'milp (OPTIMAL)': '#10b981',
};

export default function BenchmarkPage() {
  const { data: demo, isLoading: planLoading } = useQuery({ queryKey: ['planDemo'], queryFn: api.getPlanDemo });
  const { data: bm, isLoading, error } = useQuery<Benchmark | null>({
    queryKey: ['benchmark', demo?.plan?.id],
    queryFn: () => api.getBenchmark(demo?.plan?.id),
    enabled: !!demo?.plan?.id,
  });

  if (planLoading || isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span className="text-sm">Loading solver benchmarks; this may take several seconds.</span>
      </div>
    );
  }
  if (error) return <div role="alert" className="flex-1 flex items-center justify-center text-red-600">{error.message}</div>;
  if (!bm) return <div className="flex-1 flex items-center justify-center text-slate-400">Run the optimizer in this session to load its benchmark data.</div>;

  const rows = bm.benchmark;
  const gap = bm.gap_qubo_to_milp_pct;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Benchmark Comparison</h1>

      {/* Gap badge */}
      <div className="flex items-center gap-3 flex-wrap">
        {gap != null && (
          <span className="text-sm px-4 py-1.5 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200 flex items-center gap-2">
            <Zap className="w-4 h-4" />
            QUBO Gap to MILP Optimum: {gap.toFixed(2)}%
          </span>
        )}
        {bm.zoning.maxcut && (
          <span className="text-sm px-4 py-1.5 rounded-full bg-purple-50 text-purple-700 font-medium border border-purple-200">
            Max-Cut Zoning: {bm.zoning.maxcut.tier} (ratio {bm.zoning.maxcut.approx_ratio?.toFixed(2) ?? '—'})
          </span>
        )}
      </div>

      {/* Objective chart */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-700 mb-4">Solver Objective Comparison</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={rows} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="solver" tick={{ fontSize: 11 }} angle={-15} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="objective" name="Objective" radius={[4, 4, 0, 0]}>
              {rows.map((r, i) => (
                <Cell key={i} fill={SOLVER_COLORS[r.solver] ?? '#64748b'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Shortage reduction chart */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-sm font-medium text-slate-700 mb-4">Shortage Reduction by Solver</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={rows} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="solver" tick={{ fontSize: 11 }} angle={-15} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
            <Tooltip formatter={(v) => `${(Number(v) * 100).toFixed(1)}%`} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            <Bar dataKey="shortage_reduction" name="Shortage Reduction" fill="#14b8a6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wide">
              <th className="text-left px-4 py-2.5 font-medium">Solver</th>
              <th className="text-right px-4 py-2.5 font-medium">Objective</th>
              <th className="text-right px-4 py-2.5 font-medium">Shortage Red.</th>
              <th className="text-right px-4 py-2.5 font-medium">Expiry Avoided</th>
              <th className="text-right px-4 py-2.5 font-medium">Waste Moved</th>
              <th className="text-right px-4 py-2.5 font-medium">Trips</th>
              <th className="text-right px-4 py-2.5 font-medium">Time (ms)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.solver} className={cn(
                'border-t border-slate-100',
                r.solver.includes('milp') && 'bg-teal-50/50',
                r.solver.includes('qubo') && 'bg-purple-50/50',
              )}>
                <td className="px-4 py-2.5 font-medium flex items-center gap-2">
                  {r.solver.includes('milp') && <Award className="w-3.5 h-3.5 text-teal-600" />}
                  {r.solver}
                </td>
                <td className="px-4 py-2.5 text-right font-mono">{r.objective.toFixed(2)}</td>
                <td className="px-4 py-2.5 text-right font-mono">{formatPct(r.shortage_reduction)}</td>
                <td className="px-4 py-2.5 text-right font-mono">{r.expiry_avoided_inr.toLocaleString()}</td>
                <td className="px-4 py-2.5 text-right font-mono">{r.waste_moved}</td>
                <td className="px-4 py-2.5 text-right font-mono">{r.trips}</td>
                <td className="px-4 py-2.5 text-right font-mono">{r.time_ms.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Zoning comparison */}
      <h2 className="text-lg font-semibold text-slate-700 mt-2 flex items-center gap-2">
        <GitCompare className="w-5 h-5" /> Zoning Comparison
      </h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {bm.zoning.maxcut && (
          <ZoningCard
            title="QAOA Max-Cut"
            partition={bm.zoning.maxcut.partition}
            cutValue={bm.zoning.maxcut.cut_value}
            intraCost={bm.zoning.maxcut.intra_zone_cost}
            tier={bm.zoning.maxcut.tier}
            ratio={bm.zoning.maxcut.approx_ratio}
          />
        )}
        {bm.zoning.kmeans && (
          <ZoningCard
            title="k-means"
            partition={bm.zoning.kmeans.partition}
            cutValue={bm.zoning.kmeans.cut_value}
            intraCost={bm.zoning.kmeans.intra_zone_cost}
          />
        )}
        {bm.zoning.exact && (
          <ZoningCard
            title="Exact Brute-Force"
            partition={bm.zoning.exact.partition}
            cutValue={bm.zoning.exact.cut_value}
            intraCost={bm.zoning.exact.intra_zone_cost}
            tier="exact"
          />
        )}
      </div>
    </div>
  );
}

function ZoningCard({ title, partition, cutValue, intraCost, tier, ratio }: {
  title: string; partition: Record<string, number>; cutValue: number; intraCost: number;
  tier?: string; ratio?: number | null;
}) {
  const zones = Object.entries(partition).reduce<Record<number, string[]>>((acc, [fac, z]) => {
    (acc[z] ??= []).push(fac);
    return acc;
  }, {});

  const ZONE_COLORS = ['bg-blue-100 text-blue-700 border-blue-200', 'bg-amber-100 text-amber-700 border-amber-200', 'bg-teal-100 text-teal-700 border-teal-200'];

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
        {tier && <span className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-700">{tier}</span>}
      </div>
      <div className="space-y-2 mb-3">
        {Object.entries(zones).map(([z, facs]) => (
          <div key={z} className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-500 w-14">Zone {z}:</span>
            <div className="flex gap-1 flex-wrap">
              {facs.map(f => (
                <span key={f} className={cn('text-xs px-2 py-0.5 rounded border font-medium', ZONE_COLORS[Number(z)] ?? ZONE_COLORS[0])}>
                  {f}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-xs text-slate-500">
        <span>Cut value: <span className="font-mono font-medium text-slate-700">{cutValue.toFixed(2)}</span></span>
        <span>Intra-zone cost: <span className="font-mono font-medium text-slate-700">{intraCost.toLocaleString()}</span></span>
        {ratio != null && <span>Approx ratio: <span className="font-mono font-medium text-slate-700">{ratio.toFixed(2)}</span></span>}
      </div>
    </div>
  );
}
