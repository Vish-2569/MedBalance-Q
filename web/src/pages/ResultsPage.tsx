import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Trophy, Package, Truck, ShieldCheck, Loader2, Info, HelpCircle,
  ChevronDown, ChevronUp, BarChart3, PieChartIcon, FlaskConical, ArrowRight,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, ErrorBar } from 'recharts';
import { api } from '@/lib/api';
import { cn, formatPct, formatINR } from '@/lib/utils';
import { resultMetrics as demoResultMetrics } from '@/fixtures';

const COLORS = ['#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

export default function ResultsPage() {
  const { data: demo, isLoading, error } = useQuery({ queryKey: ['planDemo'], queryFn: api.getPlanDemo });
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => api.getPositions() });
  const [showGuide, setShowGuide] = useState(true);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (error || !demo) {
    return (
      <div role="alert" className="flex-1 flex flex-col items-center justify-center text-slate-500 gap-3 py-12">
        <Trophy className="w-12 h-12 text-slate-300" />
        <p className="text-base font-medium text-slate-700">No Results Yet</p>
        <p className="text-sm max-w-md text-center">
          {error instanceof Error
            ? error.message
            : 'Run the optimizer on the Plan page first to generate transfer orders. Results will appear here showing how much shortage was reduced and medicines saved.'}
        </p>
      </div>
    );
  }

  const orders = demo.orders;
  const plan = demo.plan;
  const movedUnits = orders.reduce((total, order) => total + order.qty, 0);
  const byDrug = orders.reduce<Record<string, number>>((acc, order) => {
    acc[order.drug_name] = (acc[order.drug_name] ?? 0) + order.qty;
    return acc;
  }, {});
  const chartData = Object.entries(byDrug).map(([name, qty]) => ({ name: name.split(' ')[0], qty }));
  const shortageData = positions
    .filter(position => position.shortage > 0)
    .map(position => ({ name: `${position.facility_id}-${position.drug_code}`, shortage: position.shortage }));

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Results Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Shows the measurable impact of the redistribution plan — how many shortages were reduced, medicines saved from expiry, and at what cost.
          </p>
          {demo.plan_id && <p className="text-xs text-slate-400 mt-1">Plan {demo.plan_id}</p>}
        </div>
        <div className="flex items-center gap-2">
          {plan && (
            <span className="text-xs px-3 py-1 rounded-full bg-teal-50 text-teal-700 font-medium flex items-center gap-1">
              <ShieldCheck className="w-3 h-3" />
              {formatPct(plan.shortage_reduction)} shortage reduced
            </span>
          )}
          <button
            onClick={() => setShowGuide(g => !g)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            {showGuide ? 'Hide Guide' : 'Show Guide'}
          </button>
        </div>
      </div>

      {/* Guide panel */}
      {showGuide && (
        <div className="bg-gradient-to-r from-sky-50 to-indigo-50 rounded-xl border border-sky-200 p-5">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-5 h-5 text-sky-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 text-sm mb-2">Understanding Results</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-slate-600">
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <Trophy className="w-4 h-4 text-teal-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Shortage Reduction</span>
                      <p className="text-xs text-slate-500">The percentage of district-wide medicine shortages eliminated by the plan. Higher is better.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <Package className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">At-risk Units Redistributed</span>
                      <p className="text-xs text-slate-500">Near-expiry medicines moved to facilities that can use them before they expire, preventing wastage.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <BarChart3 className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Units by Drug (bar chart)</span>
                      <p className="text-xs text-slate-500">Shows how many units of each medicine type are being transferred in the plan.</p>
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex items-start gap-2">
                    <PieChartIcon className="w-4 h-4 text-violet-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Remaining Shortages (pie chart)</span>
                      <p className="text-xs text-slate-500">Shortages that still exist after the plan. Ideally this should be small or empty.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <FlaskConical className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                    <div>
                      <span className="font-medium text-slate-700">Policy Ablation</span>
                      <p className="text-xs text-slate-500">A statistical comparison of different strategies across 20 simulation runs. The "[Illustrative]" tag means this data is from offline replay, not live results.</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2 bg-amber-50/60 rounded-lg px-2 py-1.5 border border-amber-100">
                    <Info className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-700">
                      <strong>Important:</strong> Higher shortage reduction doesn't always mean a better plan — the QUBO optimizer balances 5 objectives (shortage, expiry, cost, overfill, batching) while greedy methods only optimize one.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {demo.persisted === false && (
        <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {demo.persistence_error
            ? `These are optimizer results, but order persistence could not be verified: ${demo.persistence_error}`
            : 'These are optimizer results, but core-api did not persist the orders. Order approvals and details are unavailable for this run.'}
        </div>
      )}
      {!plan && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500">
          This saved order list has no associated optimizer metrics. Run the optimizer on the Plan page to view its measured results.
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard icon={Truck} label="Transfer Orders" value={String(orders.length)} color="text-blue-600"
          tooltip="Total number of medicine transfer orders generated by the optimizer" />
        <MetricCard icon={Package} label="Units Proposed" value={movedUnits.toLocaleString()} color="text-blue-600"
          tooltip="Total quantity of medicine units proposed to be moved across all orders" />
        <MetricCard
          icon={Trophy}
          label="Shortage Reduction"
          value={plan ? formatPct(plan.shortage_reduction) : 'Unavailable'}
          color="text-teal-600"
          tooltip="Percentage of district-wide shortages eliminated by the redistribution plan"
        />
        <MetricCard
          icon={Package}
          label="At-risk units redistributed"
          value={plan ? `${plan.expiry_avoided.toLocaleString()} units` : 'Unavailable'}
          sub={plan ? `Moved before expiry · Cost: ${formatINR(plan.cost_inr)}` : undefined}
          color="text-amber-600"
          tooltip="Near-expiry medicines moved to facilities that can use them before they expire"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-1">Units Proposed by Drug</h3>
          <p className="text-xs text-slate-400 mb-3">How many units of each medicine type are being transferred in the plan.</p>
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
            <ChartPlaceholder label="No transfer data yet. Run the optimizer on the Plan page to generate orders." />
          )}
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-1">Current Shortages by Facility and Drug</h3>
          <p className="text-xs text-slate-400 mb-3">Remaining shortages after the plan. Smaller or empty means the plan covered most needs.</p>
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
            <ChartPlaceholder label="No remaining shortages — the plan addressed all facility needs." />
          )}
        </div>
      </div>

      {/* Ablation table and CI — from offline replay eval */}
      {(() => {
        const rm = demoResultMetrics;
        const ablationChart = rm.ablation.map(row => {
          const pct = row.shortage_reduction * 100;
          return {
            name: row.variant.split(' — ')[0],
            reduction: pct,
            errorY: row.variant.includes('QUBO') ? [
              (rm.shortage_reduction - rm.ci_lower) * 100,
              (rm.ci_upper - rm.shortage_reduction) * 100,
            ] : undefined,
          };
        });
        return (
          <>
            {/* Ablation intro */}
            <div className="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
              <FlaskConical className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                <strong>Policy Ablation</strong> compares different redistribution strategies across multiple simulation runs (20 random seeds × 28 simulated days each)
                to show which approach works best overall. This provides statistical evidence beyond a single run.
              </span>
            </div>

            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Trophy className="w-5 h-5 text-amber-500" />
                <h3 className="text-sm font-semibold text-slate-600">Policy Ablation (20 seeds × 28 days)</h3>
                <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-600 border border-sky-200" title="These results are from offline replay evaluation, not live provider telemetry">[Illustrative]</span>
              </div>
              <div className="flex items-center gap-2 mb-1 text-xs text-slate-500">
                <Info className="w-3.5 h-3.5 shrink-0" />
                <span>Baseline: {rm.stockout_days_before} stockout-days. QUBO 95% CI: [{formatPct(rm.ci_lower)}, {formatPct(rm.ci_upper)}]</span>
              </div>
              <p className="text-xs text-slate-500 mb-3 ml-5">
                Greedy baselines optimise shortage filling only. QUBO/MILP balance 5 objectives
                (shortage, expiry, cost, overfill, batching) — lower shortage reduction reflects a deliberate multi-objective tradeoff.
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={ablationChart}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 12 }} unit="%" />
                  <Tooltip formatter={(v) => [`${Number(v).toFixed(1)}%`, 'Shortage ↓']} />
                  <Bar dataKey="reduction" fill="#14b8a6" radius={[4, 4, 0, 0]}>
                    <ErrorBar dataKey="errorY" width={6} strokeWidth={2} stroke="#334155" />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-600 mb-1">Ablation Detail</h3>
              <p className="text-xs text-slate-400 mb-3">
                Full breakdown of each strategy's performance. "No transfer" is the baseline (doing nothing). "MILP" is the mathematically perfect solution (too slow for real-time).
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm min-w-[600px]">
                  <thead>
                    <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                      <th className="text-left px-3 py-2 font-medium">Variant</th>
                      <th className="text-right px-3 py-2 font-medium">Shortage ↓</th>
                      <th className="text-right px-3 py-2 font-medium">At-risk Moved</th>
                      <th className="text-right px-3 py-2 font-medium">Cost</th>
                      <th className="text-left px-3 py-2 font-medium">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rm.ablation.map(row => (
                      <tr key={row.variant} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-3 py-2 font-medium text-slate-700">{row.variant}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatPct(row.shortage_reduction)}</td>
                        <td className="px-3 py-2 text-right font-mono">{row.expiry_avoided.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatINR(row.cost_inr)}</td>
                        <td className="px-3 py-2 text-xs text-slate-500">{row.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        );
      })()}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, sub, color, tooltip }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
  color?: string;
  tooltip?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3" title={tooltip}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-500" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className={cn('text-2xl font-bold', color ?? 'text-slate-800')}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function ChartPlaceholder({ label }: { label: string }) {
  return (
    <div className="h-[220px] flex flex-col items-center justify-center text-slate-400 gap-2">
      <BarChart3 className="w-8 h-8" />
      <p className="text-sm text-center max-w-xs">{label}</p>
    </div>
  );
}
