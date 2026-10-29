import { useQuery } from '@tanstack/react-query';
import { BarChart3, Cpu, Clock, TrendingDown } from 'lucide-react';
import { api } from '@/lib/api';

export default function BenchmarkPage() {
  const { data: benchmark } = useQuery({ queryKey: ['benchmark'], queryFn: api.getBenchmark });

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Solver Benchmark</h1>

      {benchmark ? (
        <div className="grid grid-cols-2 gap-4 max-w-xl">
          <Card icon={Cpu} label="Solver Tier" value={benchmark.solver_tier} />
          <Card icon={Clock} label="Solve Time" value={`${benchmark.solve_time_ms} ms`} />
          <Card icon={TrendingDown} label="QUBO Energy" value={benchmark.energy.toFixed(2)} />
          <Card icon={BarChart3} label="Gap to MILP" value={`${(benchmark.gap * 100).toFixed(1)}%`} sub={`MILP energy: ${benchmark.milp_energy.toFixed(2)}`} />
        </div>
      ) : (
        <Placeholder icon={BarChart3} text="Run a plan to see solver benchmark results" />
      )}
    </div>
  );
}

function Card({ icon: Icon, label, value, sub }: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-teal-600" />
        <span className="text-sm text-slate-500 font-medium">{label}</span>
      </div>
      <p className="text-xl font-bold text-slate-800">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
    </div>
  );
}

function Placeholder({ icon: Icon, text }: { icon: React.ComponentType<{ className?: string }>; text: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-2 py-12">
      <Icon className="w-10 h-10" />
      <p className="text-sm">{text}</p>
    </div>
  );
}
