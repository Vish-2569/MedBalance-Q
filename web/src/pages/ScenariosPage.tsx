import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Beaker, Play, CheckCircle } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

export default function ScenariosPage() {
  const queryClient = useQueryClient();
  const { data: scenarios = [] } = useQuery({ queryKey: ['scenarios'], queryFn: api.getScenarios });

  const activateMut = useMutation({
    mutationFn: (name: string) => api.activateScenario(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
  });

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Simulation Scenarios</h1>

      <div className="grid gap-3 max-w-xl">
        {scenarios.map(s => (
          <div key={s.name} className={cn(
            'bg-white rounded-lg border p-4 flex items-center justify-between',
            s.active ? 'border-teal-300 bg-teal-50' : 'border-slate-200',
          )}>
            <div>
              <div className="flex items-center gap-2">
                <Beaker className={cn('w-4 h-4', s.active ? 'text-teal-600' : 'text-slate-400')} />
                <h3 className="font-semibold text-slate-800">{s.name}</h3>
                {s.active && (
                  <span className="text-xs bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded font-medium">ACTIVE</span>
                )}
              </div>
              <p className="text-sm text-slate-500 mt-1">{s.description}</p>
            </div>
            {s.active ? (
              <CheckCircle className="w-5 h-5 text-teal-500 shrink-0" />
            ) : (
              <button
                onClick={() => activateMut.mutate(s.name)}
                disabled={activateMut.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors shrink-0"
              >
                <Play className="w-3.5 h-3.5" />
                Activate
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
