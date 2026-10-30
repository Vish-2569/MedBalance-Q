import { useQuery } from '@tanstack/react-query';
import {
  Trophy, Package, Truck, ShieldCheck, AlertTriangle, Loader2,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '@/lib/api';
import { cn, formatPct, formatINR } from '@/lib/utils';

const COLORS = ['#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

export default function ResultsPage() {
  const { data: demo, isLoading, error } = useQuery({ queryKey: ['planDemo'], queryFn: api.getPlanDemo });
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => api.getPositions() });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (error || !demo) {
    return (
      <div role="alert" className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
        <Trophy className="w-10 h-10" />
        <p className="text-sm">{error instanceof Error ? error.message : 'Could not load plan results.'}</p>
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Results Dashboard</h1>
          {demo.plan_id && <p className="text-xs text-slate-400 mt-1">Plan {demo.plan_id}</p>}
        </div>
        {plan && (
          <span className="text-xs px-3 py-1 rounded-full bg-teal-50 text-teal-700 font-medium flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" />
            {formatPct(plan.shortage_reduction)} shortage reduced
          </span>
        )}
      </div>

      {demo.persisted === false && (
        <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          {demo.persistence_error
            ? `These are optimizer results, but order persistence could not be verified: ${demo.persistence_error}`
            : 'These are optimizer results, but core-api did not persist the orders. Order approvals and details are unavailable for this run.'}
        </div>
      )}
      {!plan && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500">
          This saved order list has no associated optimizer metrics. Run the optimizer to view its measured results.
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <MetricCard icon={Truck} label="Transfer Orders" value={String(orders.length)} color="text-blue-600" />
        <MetricCard icon={Package} label="Units Proposed" value={movedUnits.toLocaleString()} color="text-blue-600" />
        <MetricCard
          icon={Trophy}
          label="Shortage Reduction"
          value={plan ? formatPct(plan.shortage_reduction) : 'Unavailable'}
          color="text-teal-600"
        />
        <MetricCard
          icon={Package}
          label="Expiry Avoided"
          value={plan ? `${plan.expiry_avoided.toLocaleString()} units` : 'Unavailable'}
          sub={plan ? `Estimated cost: ${formatINR(plan.cost_inr)}` : undefined}
          color="text-amber-600"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <h3 className="text-sm font-semibold text-slate-600 mb-3">Units Proposed by Drug</h3>
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
          <h3 className="text-sm font-semibold text-slate-600 mb-3">Current Shortages by Facility and Drug</h3>
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
            <ChartPlaceholder label="No current shortages" />
          )}
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-500 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 shrink-0 text-amber-500" />
        The live API does not expose stockout-day confidence intervals or policy-ablation results; these are intentionally not estimated here.
      </div>
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
