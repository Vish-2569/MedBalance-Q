import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Play, Pause, RotateCcw, Zap, Clock, Activity, Loader2, Radio,
  FastForward, Check, Info, AlertTriangle, Thermometer, FileWarning,
  Wrench, Construction, Syringe, Heart, TrendingUp,
  ArrowRight, Eye, ChevronDown, ChevronUp, HelpCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn, shortDate } from '@/lib/utils';
import type { Scenario, Signal } from '@/types/domain';

const SPEED_OPTIONS = [0.5, 1, 2, 5, 10];

const SCENARIO_DETAILS: Record<string, {
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  activeBg: string;
  impact: string;
  whatToObserve: string[];
  affectedPages: string[];
}> = {
  baseline: {
    icon: Heart,
    color: 'text-slate-500',
    activeBg: 'bg-slate-50 border-slate-200',
    impact: 'Normal operations with no disruptions. Use this as your control case.',
    whatToObserve: [
      'All facilities operate at normal consumption rates',
      'No alerts or excursions appear',
    ],
    affectedPages: ['Dashboard', 'Results'],
  },
  dengue_outbreak: {
    icon: AlertTriangle,
    color: 'text-red-600',
    activeBg: 'bg-red-50 border-red-200',
    impact: 'Triples ORS and Paracetamol demand at facility H3 (Yelahanka) for 10 days, simulating a sudden disease outbreak.',
    whatToObserve: [
      'H3 develops critical shortages for ORS and Paracetamol on the Dashboard map',
      'The optimizer generates new transfer orders to rush supplies to H3 (Plan page)',
      'Forecast service detects the demand spike and adjusts predictions',
      'Copilot can explain why H3 is suddenly short on medicines',
    ],
    affectedPages: ['Dashboard', 'Plan', 'Results', 'Copilot'],
  },
  fridge_failure: {
    icon: Thermometer,
    color: 'text-orange-600',
    activeBg: 'bg-orange-50 border-orange-200',
    impact: 'Simulates cold van CV-02 compressor failure. Temperature rises to 18.5°C, far above the safe 2–8°C range.',
    whatToObserve: [
      'A red COLD CHAIN EXCURSION banner appears at the top of every page',
      'Cold Chain page shows CV-02 in excursion state with temperature spike on sparkline',
      'Optimizer blocks cold-chain transfers through CV-02 (feasibility rule F3)',
      'Any insulin or vaccine lots in transit via CV-02 are flagged for quarantine',
    ],
    affectedPages: ['Cold Chain', 'Plan', 'Dashboard'],
  },
  bad_data: {
    icon: FileWarning,
    color: 'text-amber-600',
    activeBg: 'bg-amber-50 border-amber-200',
    impact: 'Facility H4 sends a garbled stock report with OCR errors and mismatched batch numbers.',
    whatToObserve: [
      'Ingestion page shows the H4 report flagged with data quality issues',
      'Review queue gets new items needing pharmacist correction',
      'AI extraction confidence scores drop for H4 items',
      'Demonstrates the human-in-the-loop review safety net',
    ],
    affectedPages: ['Ingestion', 'AI Health'],
  },
  ilr_repaired: {
    icon: Wrench,
    color: 'text-teal-600',
    activeBg: 'bg-teal-50 border-teal-200',
    impact: 'Ice-Lined Refrigerator at H4 is repaired and validated, restoring cold storage capability.',
    whatToObserve: [
      'H4 becomes eligible for cold-chain drug transfers (insulin, vaccines)',
      'Re-running the optimizer may generate new orders to H4 for cold-chain drugs',
      'Cold Chain page shows the device fault cleared',
    ],
    affectedPages: ['Plan', 'Cold Chain', 'Dashboard'],
  },
  road_closure: {
    icon: Construction,
    color: 'text-violet-600',
    activeBg: 'bg-violet-50 border-violet-200',
    impact: 'Blocks road routes between H3 and H1, preventing direct transfers between these facilities.',
    whatToObserve: [
      'Optimizer skips H3↔H1 transfers (feasibility rule F2: route not available)',
      'Plan page may show alternative routing through other facilities',
      'Copilot "why not" queries explain the blocked route',
    ],
    affectedPages: ['Plan', 'Dashboard', 'Copilot'],
  },
  td_campaign: {
    icon: Syringe,
    color: 'text-blue-600',
    activeBg: 'bg-blue-50 border-blue-200',
    impact: 'Doubles Tetanus-Diphtheria (TD) vaccine demand at H1 for 7 days, simulating a planned immunization campaign.',
    whatToObserve: [
      'H1 develops increased TD shortage on the Dashboard',
      'Optimizer prioritizes TD transfers to H1 in the next plan run',
      'Unlike the outbreak scenario, this is a planned event with a known duration',
    ],
    affectedPages: ['Dashboard', 'Plan', 'Results'],
  },
};

const SIGNAL_TYPE_INFO: Record<string, {
  label: string;
  description: string;
  color: string;
  bg: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  outbreak: {
    label: 'Disease Outbreak',
    description: 'A disease outbreak has been reported, causing a sudden demand spike for specific medicines.',
    color: 'text-red-700',
    bg: 'bg-red-50 border-red-200',
    icon: AlertTriangle,
  },
  device_fault: {
    label: 'Equipment Failure',
    description: 'A cold chain device has malfunctioned, potentially compromising temperature-sensitive medicines.',
    color: 'text-orange-700',
    bg: 'bg-orange-50 border-orange-200',
    icon: Thermometer,
  },
  data_quality: {
    label: 'Data Quality Issue',
    description: 'A hospital report contains errors or inconsistencies that need manual review.',
    color: 'text-amber-700',
    bg: 'bg-amber-50 border-amber-200',
    icon: FileWarning,
  },
  equipment_repair: {
    label: 'Equipment Repaired',
    description: 'A previously faulty device has been repaired and validated, restoring normal operations.',
    color: 'text-teal-700',
    bg: 'bg-teal-50 border-teal-200',
    icon: Wrench,
  },
  route_closure: {
    label: 'Route Blocked',
    description: 'A transport route is closed, preventing medicine transfers along that path.',
    color: 'text-violet-700',
    bg: 'bg-violet-50 border-violet-200',
    icon: Construction,
  },
  campaign: {
    label: 'Immunization Campaign',
    description: 'A planned vaccination or immunization drive is underway, increasing demand for specific drugs.',
    color: 'text-blue-700',
    bg: 'bg-blue-50 border-blue-200',
    icon: Syringe,
  },
  dengue_season: {
    label: 'Seasonal Alert',
    description: 'A seasonal disease pattern is expected, slightly increasing demand for related medicines across the district.',
    color: 'text-amber-700',
    bg: 'bg-amber-50 border-amber-200',
    icon: TrendingUp,
  },
};

function humanizeSignalParams(signal: { id: string; type: string; params: Record<string, unknown> }): string {
  const p = signal.params;
  const facility = p.facility_id as string | undefined;
  const drug = (p.drug_code as string) ?? (p.affects as string[] | undefined)?.join(', ');
  const multiplier = p.demand_multiplier as number | undefined;

  switch (signal.type) {
    case 'outbreak':
      return `${drug ?? 'Multiple drugs'} demand ${multiplier ? `${multiplier}x` : 'surging'} at ${facility ?? 'district'}`;
    case 'device_fault':
      return `Cold chain device failure${facility ? ` near ${facility}` : ''}`;
    case 'data_quality':
      return `Garbled stock report from ${facility ?? 'unknown facility'}`;
    case 'equipment_repair':
      return `Cold storage restored at ${facility ?? 'facility'}`;
    case 'route_closure':
      return `Road closed${facility ? ` affecting routes through ${facility}` : ''}`;
    case 'campaign':
      return `${drug ?? 'Vaccine'} campaign${facility ? ` at ${facility}` : ''}, demand ${multiplier ? `${multiplier}x` : 'increased'}`;
    case 'dengue_season': {
      const affects = p.affects as string[] | undefined;
      const factor = p.factor as number | undefined;
      return `Seasonal dengue pattern — ${affects?.join(', ') ?? 'multiple drugs'} demand ${factor ? `${factor}x` : 'elevated'} district-wide`;
    }
    default:
      return JSON.stringify(p);
  }
}

export default function ScenariosPage() {
  const queryClient = useQueryClient();
  const { data: scenarios = [], isLoading, error: scenariosError } = useQuery({ queryKey: ['scenarios'], queryFn: api.getScenarios });
  const { data: signals = [], error: signalsError } = useQuery({ queryKey: ['signals'], queryFn: api.getSignals });
  const { data: clock, error: clockError } = useQuery({ queryKey: ['clock'], queryFn: api.getClock, refetchInterval: 2000 });
  const queryError = scenariosError ?? signalsError ?? clockError;
  const [seed, setSeed] = useState('42');
  const [showGuide, setShowGuide] = useState(true);

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

  if (isLoading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-6 h-6 animate-spin text-slate-500" /></div>;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Scenario Console</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Inject real-world disruptions into the simulation and observe how the system responds.
          </p>
        </div>
        <button
          onClick={() => setShowGuide(g => !g)}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          {showGuide ? 'Hide Guide' : 'Show Guide'}
        </button>
      </div>

      {queryError && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Failed to load scenario data: {queryError.message}
        </div>
      )}
      {[startMut.error, pauseMut.error, speedMut.error, activateMut.error, resetMut.error]
        .filter((error): error is Error => error instanceof Error)
        .map((error, index) => (
          <div key={`${error.message}-${index}`} role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error.message}
          </div>
        ))}

      {/* Getting Started Guide */}
      {showGuide && (
        <div className="bg-gradient-to-r from-sky-50 to-indigo-50 rounded-xl border border-sky-200 p-5">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-5 h-5 text-sky-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-slate-800 text-sm mb-2">How Scenarios Work</h3>
              <p className="text-sm text-slate-600 leading-relaxed mb-3">
                Scenarios simulate real-world disruptions that a district health system might face — disease outbreaks,
                equipment failures, blocked roads, or bad data. When you <strong>activate</strong> a scenario, it injects
                changes into the simulation (like tripling medicine demand or breaking a fridge), and you can then observe
                how MedBalance-Q detects and responds to each situation.
              </p>
              <div className="bg-white/70 rounded-lg p-3 mb-3">
                <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wide mb-2">Quick Start — Try This</h4>
                <ol className="text-sm text-slate-600 space-y-1.5">
                  <li className="flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">1</span>
                    <span>Press <strong>Play</strong> on the simulation clock below to start time advancing</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">2</span>
                    <span>Click <strong>Activate</strong> on the <strong>"dengue_outbreak"</strong> scenario</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">3</span>
                    <span>A signal will appear in the <strong>Recent Signals</strong> table showing the outbreak alert</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">4</span>
                    <span>Go to the <strong>Dashboard</strong> to see H3 turn red (shortage), then <strong>Plan</strong> to run the optimizer</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="w-5 h-5 rounded-full bg-teal-100 text-teal-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">5</span>
                    <span>Check <strong>Results</strong> to see how much shortage was reduced</span>
                  </li>
                </ol>
              </div>
              <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                <span className="flex items-center gap-1"><RotateCcw className="w-3 h-3" /> Use <strong>Reset</strong> to clear all scenarios and start fresh</span>
                <span className="flex items-center gap-1"><Zap className="w-3 h-3" /> You can activate multiple scenarios at once</span>
                <span className="flex items-center gap-1"><FastForward className="w-3 h-3" /> Speed up the clock to see effects faster</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Clock controls */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1 flex items-center gap-1">
          <Clock className="w-3 h-3" /> Simulation Clock
        </h3>
        <p className="text-xs text-slate-400 mb-3">Controls the virtual time. Each "day" represents a full cycle of hospital consumption, reporting, and redistribution.</p>
        <div className="flex items-center gap-4 flex-wrap">
          {clock && (
            <div className="flex items-center gap-2">
              <span className={cn('w-2 h-2 rounded-full', clock.running ? 'bg-teal-500 animate-pulse' : 'bg-slate-400')} />
              <span className="font-mono text-lg font-semibold text-slate-800">{clock.sim_date}</span>
              <span className="text-xs text-slate-500">Day {clock.day_index}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">{clock.speed}x speed</span>
            </div>
          )}

          <div className="flex items-center gap-1 border border-slate-200 rounded-lg p-1">
            <button onClick={() => startMut.mutate()} disabled={startMut.isPending || clock?.running}
              className="p-1.5 rounded hover:bg-teal-50 text-teal-600 disabled:opacity-40" title="Start the simulation clock">
              <Play className="w-4 h-4" />
            </button>
            <button onClick={() => pauseMut.mutate()} disabled={pauseMut.isPending || !clock?.running}
              className="p-1.5 rounded hover:bg-amber-50 text-amber-600 disabled:opacity-40" title="Pause the simulation clock">
              <Pause className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-1">
            <FastForward className="w-3.5 h-3.5 text-slate-500" />
            {SPEED_OPTIONS.map(s => (
              <button key={s} onClick={() => speedMut.mutate(s)}
                title={`Set simulation speed to ${s}x`}
                className={cn(
                  'text-xs px-2 py-1 rounded font-mono',
                  clock?.speed === s ? 'bg-teal-100 text-teal-700 font-semibold' : 'text-slate-500 hover:bg-slate-100',
                )}>
                {s}x
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <label htmlFor="sim-seed" className="text-xs text-slate-500">Seed:</label>
            <input id="sim-seed" value={seed} onChange={e => setSeed(e.target.value)}
              title="Random seed for reproducible simulations"
              className="w-20 border border-slate-200 rounded px-2 py-1 text-xs font-mono" placeholder="seed" />
            <button onClick={() => resetMut.mutate()} disabled={resetMut.isPending}
              title="Reset simulation: clears all scenarios, restores all hospitals to initial state"
              className="flex items-center gap-1 text-xs px-3 py-1.5 border border-slate-300 rounded-lg hover:bg-slate-50 text-slate-600">
              {resetMut.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
              Reset All
            </button>
          </div>
        </div>
      </div>

      {/* Active scenarios */}
      {active.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-1 flex items-center gap-2">
            <Radio className="w-4 h-4 text-teal-500" /> Active Scenarios
          </h3>
          <p className="text-xs text-slate-400 mb-2">These disruptions are currently affecting the simulation. Their effects will appear across the system.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {active.map(s => <ScenarioCard key={s.id ?? s.name} scenario={s} isActive />)}
          </div>
        </div>
      )}

      {/* Available scenarios */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Available Scenarios</h3>
        <p className="text-xs text-slate-400 mb-2">Click "Activate" on any scenario to inject that disruption into the simulation.</p>
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
        <h3 className="text-sm font-semibold text-slate-700 mb-1 flex items-center gap-2">
          <Activity className="w-4 h-4" /> Recent Signals
        </h3>
        <p className="text-xs text-slate-400 mb-2">
          When a scenario is activated, it fires signals — these are the alerts and events that the system
          detects and responds to (like an outbreak notification or equipment failure warning).
        </p>
        {signals.length > 0 ? (
          <div className="space-y-2">
            {signals.map(s => <SignalCard key={s.id} signal={s} />)}
          </div>
        ) : (
          <div className="bg-slate-50 rounded-lg border border-slate-200 p-6 text-center">
            <Activity className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500 font-medium">No signals fired yet</p>
            <p className="text-xs text-slate-400 mt-1">Activate a scenario above to see signals appear here.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function ScenarioCard({ scenario, isActive, onActivate, activating }: {
  scenario: Scenario; isActive?: boolean; onActivate?: () => void; activating?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const details = SCENARIO_DETAILS[scenario.name];
  const ScenarioIcon = details?.icon ?? Zap;
  const iconColor = details?.color ?? 'text-slate-500';

  return (
    <div className={cn(
      'rounded-lg border p-4 transition-colors',
      isActive
        ? (details?.activeBg ?? 'bg-teal-50 border-teal-200')
        : 'bg-white border-slate-200 hover:border-slate-300',
    )}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            {isActive && <span className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />}
            <ScenarioIcon className={cn('w-4 h-4 shrink-0', iconColor)} />
            <span className="font-semibold text-slate-800 text-sm">{scenario.name.replace(/_/g, ' ')}</span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{scenario.description}</p>

          {details && (
            <>
              <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                <strong className="text-slate-700">Impact:</strong> {details.impact}
              </p>

              <button
                onClick={() => setExpanded(e => !e)}
                className="flex items-center gap-1 text-xs text-teal-600 hover:text-teal-800 mt-2 font-medium"
              >
                <Eye className="w-3 h-3" />
                {expanded ? 'Hide details' : 'What to observe'}
                {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>

              {expanded && (
                <div className="mt-2 pl-1 space-y-2">
                  <ul className="text-xs text-slate-600 space-y-1">
                    {details.whatToObserve.map((item, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <ArrowRight className="w-3 h-3 text-teal-500 shrink-0 mt-0.5" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap gap-1">
                    <span className="text-xs text-slate-400">Check these pages:</span>
                    {details.affectedPages.map(page => (
                      <span key={page} className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                        {page}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        <div className="shrink-0 flex flex-col items-end gap-1.5">
          {onActivate && (
            <button onClick={onActivate} disabled={activating}
              className="flex items-center gap-1 text-xs px-3 py-1.5 bg-teal-600 text-white rounded-lg hover:bg-teal-700 disabled:opacity-50">
              {activating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
              Activate
            </button>
          )}
          {isActive && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-teal-100 text-teal-700 font-medium flex items-center gap-1">
              <Check className="w-3 h-3" /> Active
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const [expanded, setExpanded] = useState(false);
  const typeInfo = SIGNAL_TYPE_INFO[signal.type];
  const TypeIcon = typeInfo?.icon ?? Activity;
  const humanDescription = humanizeSignalParams(signal);

  return (
    <div className={cn(
      'rounded-lg border p-3 transition-colors',
      typeInfo?.bg ?? 'bg-slate-50 border-slate-200',
    )}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 flex-1">
          <div className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5',
            signal.type === 'outbreak' ? 'bg-red-100' :
            signal.type === 'device_fault' ? 'bg-orange-100' :
            signal.type === 'data_quality' ? 'bg-amber-100' :
            signal.type === 'equipment_repair' ? 'bg-teal-100' :
            signal.type === 'route_closure' ? 'bg-violet-100' :
            signal.type === 'campaign' ? 'bg-blue-100' :
            'bg-slate-100',
          )}>
            <TypeIcon className={cn('w-4 h-4', typeInfo?.color ?? 'text-slate-600')} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn('text-xs px-2 py-0.5 rounded-full font-semibold border', typeInfo?.bg ?? 'bg-slate-50 border-slate-200')}>
                {typeInfo?.label ?? signal.type}
              </span>
              <span className="text-xs text-slate-400 font-mono">{signal.id}</span>
            </div>
            <p className="text-sm text-slate-700 font-medium mt-1">{humanDescription}</p>
            {typeInfo?.description && (
              <p className="text-xs text-slate-500 mt-0.5">{typeInfo.description}</p>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="text-xs text-slate-500">
            {signal.fired_at === 'seasonal' ? 'Seasonal' : signal.fired_at ? shortDate(signal.fired_at) : 'Pending'}
          </span>
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-0.5"
          >
            {expanded ? 'Less' : 'Raw data'}
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="mt-2 ml-10.5 pl-1">
          <pre className="text-xs font-mono bg-white/60 rounded border border-slate-200 p-2 overflow-x-auto text-slate-600">
            {JSON.stringify(signal.params, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
