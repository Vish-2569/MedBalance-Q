import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { Loader2, Award, Zap, GitCompare, Info, HelpCircle, BarChart3, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatPct } from '@/lib/utils';
import type { Benchmark } from '@/types/domain';

const SOLVER_EXPLANATIONS: { name: string; color: string; description: string }[] = [
  { name: 'no-transfer', color: '#94a3b8', description: 'Baseline — no redistribution at all. Shows what happens if we do nothing.' },
  { name: 'greedy-phone-call', color: '#f59e0b', description: 'Manual ad-hoc approach — how transfers happen today without automation (phone calls between facilities).' },
  { name: 'greedy-f4', color: '#3b82f6', description: 'Algorithmic greedy — fills the biggest shortage first with feasibility checks, but only optimizes one goal.' },
  { name: 'qubo (qpiai-local)', color: '#8b5cf6', description: 'Our QUBO-based optimizer — balances 5 objectives simultaneously (shortage, expiry, cost, overfill, batching).' },
  { name: 'milp (OPTIMAL)', color: '#10b981', description: 'Mathematically exact best answer (MILP) — the theoretical optimum. Too slow for real-time use but serves as our accuracy target.' },
];

const SOLVER_COLORS: Record<string, string> = {
  'no-transfer': '#94a3b8',
  'greedy-phone-call': '#f59e0b',
  'greedy-f4': '#3b82f6',
  'qubo (qpiai-local)': '#8b5cf6',
  'milp (OPTIMAL)': '#10b981',
};

export default function BenchmarkPage() {
  const [showGuide, setShowGuide] = useState(false);
  const { data: demo, isLoading: planLoading } = useQuery({ queryKey: ['planDemo'], queryFn: api.getPlanDemo });
  const { data: bm, isLoading, error } = useQuery<Benchmark | null>({
    queryKey: ['benchmark', demo?.plan?.id],
    queryFn: () => api.getBenchmark(demo?.plan?.id),
    enabled: !!demo?.plan?.id,
  });

  if (planLoading || isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin" />
        <span className="text-sm">Loading solver benchmarks; this may take several seconds.</span>
      </div>
    );
  }
  if (error) return <div role="alert" className="flex-1 flex items-center justify-center text-red-600">{error.message}</div>;
  if (!bm) return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 text-slate-500 p-8">
      <BarChart3 className="w-12 h-12 text-slate-300" />
      <h2 className="text-lg font-semibold text-slate-700">No Benchmark Data Yet</h2>
      <p className="text-sm text-center max-w-md">
        This page compares how different optimization strategies perform at redistributing medicines.
        To see results, you need to run the optimizer first.
      </p>
      <div className="bg-slate-50 rounded-lg border border-slate-200 p-4 text-sm text-left max-w-md space-y-2">
        <p className="font-medium text-slate-700">How to get benchmark data:</p>
        <ol className="list-decimal list-inside space-y-1 text-slate-600">
          <li>Go to the <strong>Ingestion</strong> page and upload or ingest hospital stock data</li>
          <li>Go to the <strong>Plan</strong> page and run the optimizer</li>
          <li>Come back here to see how each solver performed</li>
        </ol>
      </div>
    </div>
  );

  const rows = bm.benchmark;
  const gap = bm.gap_qubo_to_milp_pct;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Benchmark Comparison</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Compares how different optimization strategies perform. Lower gap to MILP means closer to the mathematically optimal solution.
          </p>
        </div>
        <button
          onClick={() => setShowGuide(!showGuide)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
        >
          <HelpCircle className="w-4 h-4" />
          {showGuide ? 'Hide' : 'Understanding Solvers'}
          {showGuide ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {showGuide && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-semibold text-indigo-800 flex items-center gap-2">
            <BarChart3 className="w-4 h-4" /> What Are These Solvers?
          </h3>
          <p className="text-sm text-indigo-700">
            Each solver is a different strategy for deciding which medicines to move between facilities.
            We run all of them on the same data and compare their results.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {SOLVER_EXPLANATIONS.map((s) => (
              <div key={s.name} className="bg-white rounded-lg border border-indigo-100 p-3 flex items-start gap-2">
                <div className="w-3 h-3 rounded-full mt-1 shrink-0" style={{ backgroundColor: s.color }} />
                <div>
                  <span className="text-xs font-semibold text-slate-700">{s.name}</span>
                  <p className="text-xs text-slate-500 mt-0.5">{s.description}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-lg border border-indigo-100 p-3 text-xs text-slate-600 space-y-1">
            <p><strong>How to read the charts:</strong></p>
            <ul className="list-disc list-inside space-y-0.5">
              <li><strong>Objective score</strong> — higher means a better overall balance across all 5 optimization goals</li>
              <li><strong>Shortage reduction</strong> — what percentage of drug shortages were resolved by transfers</li>
              <li><strong>QUBO gap to MILP</strong> — how close our quantum-inspired optimizer gets to the perfect answer (lower = better)</li>
              <li><strong>Zoning</strong> — how facilities are grouped into delivery zones (lower intra-zone cost = more efficient routes)</li>
            </ul>
          </div>
        </div>
      )}

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

      {/* Multi-objective note */}
      <div className="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>
          Greedy baselines optimise a single objective (shortage filling). QUBO and MILP optimise five
          objectives simultaneously (shortage, expiry avoidance, cost, overfill, batch consolidation).
          Higher shortage reduction does not mean a better plan — it may move waste or ignore cost.
          We do not claim quantum advantage; see the gap to MILP optimum above.
        </span>
      </div>

      {/* Objective chart */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-700">Solver Objective Comparison</h3>
          <span className="text-xs text-slate-400">Higher score = better overall balance across 5 goals</span>
        </div>
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
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-slate-700">Shortage Reduction by Solver</h3>
          <div className="flex items-center gap-1 text-xs text-amber-600">
            <AlertTriangle className="w-3 h-3" />
            <span>Higher isn't always better — greedy methods may ignore cost and expiry</span>
          </div>
        </div>
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
      <p className="text-sm text-slate-500 -mt-2">
        Facilities are grouped into delivery zones to minimize transport cost. Lower intra-zone cost means more efficient routing.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {bm.zoning.maxcut && (
          <ZoningCard
            title="QAOA Max-Cut"
            subtitle="Quantum-inspired algorithm for zone partitioning"
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
            subtitle="Standard clustering baseline"
            partition={bm.zoning.kmeans.partition}
            cutValue={bm.zoning.kmeans.cut_value}
            intraCost={bm.zoning.kmeans.intra_zone_cost}
          />
        )}
        {bm.zoning.exact && (
          <ZoningCard
            title="Exact Brute-Force"
            subtitle="Tests every possible grouping (slow but perfect)"
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

function ZoningCard({ title, subtitle, partition, cutValue, intraCost, tier, ratio }: {
  title: string; subtitle?: string; partition: Record<string, number>; cutValue: number; intraCost: number;
  tier?: string; ratio?: number | null;
}) {
  const zones = Object.entries(partition).reduce<Record<number, string[]>>((acc, [fac, z]) => {
    (acc[z] ??= []).push(fac);
    return acc;
  }, {});

  const ZONE_COLORS = ['bg-blue-100 text-blue-700 border-blue-200', 'bg-amber-100 text-amber-700 border-amber-200', 'bg-teal-100 text-teal-700 border-teal-200'];

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between mb-1">
        <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
        {tier && <span className="text-xs px-2 py-0.5 rounded bg-purple-50 text-purple-700">{tier}</span>}
      </div>
      {subtitle && <p className="text-xs text-slate-400 mb-3">{subtitle}</p>}
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
