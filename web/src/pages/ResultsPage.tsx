import { useQuery } from '@tanstack/react-query';
import { Trophy, TrendingDown, Package, Truck } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { api } from '@/lib/api';
import { formatPct } from '@/lib/utils';

const COLORS = ['#14b8a6', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6'];

export default function ResultsPage() {
  const { data: planDemo } = useQuery({ queryKey: ['plan'], queryFn: api.getPlanDemo });
  const { data: positions = [] } = useQuery({ queryKey: ['positions'], queryFn: () => api.getPositions() });

  const plan = planDemo?.plan;
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
      <h1 className="text-xl font-semibold text-slate-800">Results Dashboard</h1>

      {plan ? (
        <>
          <div className="grid grid-cols-4 gap-3">
            <MetricCard icon={TrendingDown} label="Shortage Reduced" value={formatPct(plan.shortage_reduction)} />
            <MetricCard icon={Package} label="Expiry Avoided" value={`${plan.expiry_avoided} units`} />
            <MetricCard icon={Truck} label="Total Transfers" value={String(plan.transfers)} />
            <MetricCard icon={Trophy} label="Solver" value={plan.solver_tier.replace('qpiai-', '')} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-600 mb-3">Units Transferred by Drug</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="qty" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
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
                <div className="h-[220px] flex items-center justify-center text-slate-400 text-sm">
                  No shortages remaining
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
          <Trophy className="w-10 h-10" />
          <p className="text-sm">Run a plan to see results</p>
        </div>
      )}
    </div>
  );
}

function MetricCard({ icon: Icon, label, value }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-teal-600" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className="text-lg font-bold text-slate-800">{value}</p>
    </div>
  );
}
