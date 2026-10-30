import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Play, Pause, RotateCcw, Zap, Clock, Activity, Loader2, Radio,
  FastForward, Check,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, shortDate } from '@/lib/utils';
import type { Scenario } from '@/types/domain';

const SPEED_OPTIONS = [0.5, 1, 2, 5, 10];

export default function ScenariosPage() {
  const queryClient = useQueryClient();
  const { data: scenarios = [], isLoading } = useQuery({ queryKey: ['scenarios'], queryFn: api.getScenarios });
  const { data: signals = [] } = useQuery({ queryKey: ['signals'], queryFn: api.getSignals });
  const { data: clock } = useQuery({ queryKey: ['clock'], queryFn: api.getClock, refetchInterval: 2000 });
  const [seed, setSeed] = useState('42');

  const startMut = useMutation({ mutationFn: api.startClock, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });
  const pauseMut = useMutation({ mutationFn: api.pauseClock, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });
  const speedMut = useMutation({ mutationFn: (s: number) => api.setSpeed(s), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['clock'] }) });
  const activateMut = useMutation({
    mutationFn: (name: string) => api.activateScenario(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      void queryClient.invalidateQueries({ queryKey: ['signals'] });
    },
  });
  const resetMut = useMutation({
    mutationFn: () => api.resetSim(seed ? Number(seed) : undefined),
    onSuccess: () => queryClient.invalidateQueries(),
  });

  const active = scenarios.filter(s => s.active);
  const inactive = scenarios.filter(s => !s.active);

  if (isLoading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-400" /></div>;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">Scenario Console</h1>
      {[startMut.error, pauseMut.error, speedMut.error, activateMut.error, resetMut.error]
        .filter((error): error is Error => error instanceof Error)
        .map((error, index) => (
          <div key={`${error.message}-${index}`} role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error.message}
          </div>
        ))}

      {/* Clock controls */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1">
          <Clock className="w-3 h-3" /> Simulation Clock
        </h3>
        <div className="flex items-center gap-4 flex-wrap">
          {clock && (
            <div className="flex items-center gap-2">
              <span className={cn('w-2 h-2 rounded-full', clock.running ? 'bg-teal-500' : 'bg-slate-400')} />
              <span className="font-mono text-lg font-semibold text-slate-800">{clock.sim_date}</span>
              <span className="text-xs text-slate-500">Day {clock.day_index}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">{clock.speed}x</span>
            </div>
          )}

          <div className="flex items-center gap-1 border border-slate-200 rounded-lg p-1">
            <button onClick={() => startMut.mutate()} disabled={startMut.isPending || clock?.running}
              className="p-1.5 rounded hover:bg-teal-50 text-teal-600 disabled:opacity-40" title="Start">
              <Play className="w-4 h-4" />
            </button>
            <button onClick={() => pauseMut.mutate()} disabled={pauseMut.isPending || !clock?.running}
              className="p-1.5 rounded hover:bg-amber-50 text-amber-600 disabled:opacity-40" title="Pause">
              <Pause className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-1">
            <FastForward className="w-3.5 h-3.5 text-slate-400" />
            {SPEED_OPTIONS.map(s => (
              <button key={s} onClick={() => speedMut.mutate(s)}
                className={cn(
                  'text-xs px-2 py-1 rounded font-mono',
                  clock?.speed === s ? 'bg-teal-100 text-teal-700 font-semibold' : 'text-slate-500 hover:bg-slate-100',
                )}>
                {s}x
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <input value={seed} onChange={e => setSeed(e.target.value)}
              className="w-20 border border-slate-200 rounded px-2 py-1 text-xs font-mono" placeholder="seed" />
            <button onClick={() => resetMut.mutate()} disabled={resetMut.isPending}
              className="flex items-center gap-1 text-xs px-3 py-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 text-slate-600">
              {resetMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Active scenarios */}
      {active.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
            <Radio className="w-4 h-4 text-teal-500" /> Active Scenarios
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {active.map(s => <ScenarioCard key={s.id ?? s.name} scenario={s} isActive />)}
          </div>
        </div>
      )}

      {/* Available scenarios */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2">Available Scenarios</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {inactive.map(s => (
            <ScenarioCard key={s.id ?? s.name} scenario={s}
              onActivate={() => activateMut.mutate(s.name)}
              activating={activateMut.isPending}
            />
          ))}
        </div>
      </div>

      {/* Signals */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
          <Activity className="w-4 h-4" /> Recent Signals
        </h3>
        {signals.length > 0 ? (
          <div className="bg-white rounded-lg border border-slate-200 overflow-x-auto">
            <table className="w-full text-sm min-w-[500px]">
              <thead>
                <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                  <th className="text-left px-4 py-2 font-medium">ID</th>
                  <th className="text-left px-4 py-2 font-medium">Type</th>
                  <th className="text-left px-4 py-2 font-medium">Params</th>
                  <th className="text-left px-4 py-2 font-medium">Fired At</th>
                </tr>
              </thead>
              <tbody>
                {signals.map(s => (
                  <tr key={s.id} className="border-t border-slate-100">
                    <td className="px-4 py-2 font-mono text-xs">{s.id}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 font-medium">{s.type}</span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500 font-mono max-w-xs truncate">
                      {JSON.stringify(s.params)}
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-500">{s.fired_at === 'seasonal' ? 'seasonal' : shortDate(s.fired_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-slate-400">No signals fired yet.</p>
        )}
      </div>
    </div>
  );
}

function ScenarioCard({ scenario, isActive, onActivate, activating }: {
  scenario: Scenario; isActive?: boolean; onActivate?: () => void; activating?: boolean;
}) {
  return (
    <div className={cn(
      'rounded-lg border p-4 transition-colors',
      isActive ? 'bg-teal-50 border-teal-200' : 'bg-white border-slate-200 hover:border-slate-300',
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            {isActive && <span className="w-2 h-2 rounded-full bg-teal-500" />}
            <span className="font-semibold text-slate-800 text-sm">{scenario.name}</span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{scenario.description}</p>
        </div>
        {onActivate && (
          <button onClick={onActivate} disabled={activating}
            className="shrink-0 flex items-center gap-1 text-xs px-3 py-1.5 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50">
            {activating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            Activate
          </button>
        )}
        {isActive && (
          <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-teal-100 text-teal-700 font-medium flex items-center gap-1">
            <Check className="w-3 h-3" /> Active
          </span>
        )}
      </div>
    </div>
  );
}
