import { useQuery } from '@tanstack/react-query';
import {
  Brain, Server, Zap, Shield, AlertCircle, Activity, Info,
  Clock, Database, Loader2, RefreshCw,
} from 'lucide-react';
import { aiHealth as demoAIHealth } from '@/fixtures';
import { api } from '@/lib/api';
import { cn, formatPct } from '@/lib/utils';
import type { AIHealthData } from '@/types/domain';

export default function AIHealthPage() {
  const { data: health, isLoading, error } = useQuery<AIHealthData>({
    queryKey: ['ai-health'],
    queryFn: api.getAIHealth,
    refetchInterval: 15_000,
  });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" />
      </div>
    );
  }

  if (error || !health) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400 gap-3">
        <AlertCircle className="w-8 h-8" />
        <p>Failed to load AI Health data.</p>
      </div>
    );
  }

  const showingDemoMetrics = health.total_calls === 0;
  const metrics = showingDemoMetrics ? demoAIHealth : health;

  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-800">AI Health</h1>
        <span className={cn(
          'text-xs px-3 py-1 rounded-full font-medium',
          health.status === 'healthy' ? 'bg-teal-100 text-teal-700' : 'bg-red-100 text-red-700',
        )}>
          {health.status.toUpperCase()}
        </span>
      </div>

      {showingDemoMetrics && (
        <div className="flex items-start gap-2 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-800">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            No LLM calls were recorded in the last 24 hours. Showing illustrative demo metrics below; they are not live provider telemetry.
          </p>
        </div>
      )}

      {/* Provider info */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-5 h-5 text-teal-600" />
          <h3 className="font-semibold text-slate-700">GenAI Gateway</h3>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <InfoRow label="Provider" value={health.provider} />
          <InfoRow label="Fast Model" value={health.model_fast} />
          <InfoRow label="Smart Model" value={health.model_smart} />
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard
          icon={Activity}
          label="Total LLM Calls"
          value={metrics.total_calls == null ? 'Unavailable' : String(metrics.total_calls)}
          color="text-teal-600"
          demo={showingDemoMetrics}
        />
        <StatCard
          icon={Database}
          label="Cache Hit Rate"
          value={metrics.cache_hit_rate == null ? 'Unavailable' : formatPct(metrics.cache_hit_rate)}
          color="text-blue-600"
          sub={metrics.cache_hit_rate == null ? undefined : metrics.cache_hit_rate >= 0.5 ? 'Good' : 'Low'}
          demo={showingDemoMetrics}
        />
        <StatCard
          icon={Clock}
          label="P95 Latency"
          value={metrics.p95_latency_ms == null ? 'Unavailable' : `${metrics.p95_latency_ms}ms`}
          color={metrics.p95_latency_ms != null && metrics.p95_latency_ms > 2000 ? 'text-red-600' : 'text-slate-800'}
          demo={showingDemoMetrics}
        />
        <StatCard
          icon={AlertCircle}
          label="Schema Failures"
          value={metrics.schema_failures == null ? 'Unavailable' : String(metrics.schema_failures)}
          color={metrics.schema_failures != null && metrics.schema_failures > 5 ? 'text-red-600' : 'text-amber-600'}
          demo={showingDemoMetrics}
        />
        <StatCard
          icon={RefreshCw}
          label="Fallbacks"
          value={metrics.fallbacks == null ? 'Unavailable' : String(metrics.fallbacks)}
          color="text-amber-600"
          sub="Calls using fallback"
          demo={showingDemoMetrics}
        />
        <StatCard
          icon={Shield}
          label="Firewall Blocks"
          value={metrics.firewall_blocks == null ? 'Unavailable' : String(metrics.firewall_blocks)}
          color={metrics.firewall_blocks != null && metrics.firewall_blocks > 0 ? 'text-red-600' : 'text-teal-600'}
          sub="Narration grounding"
          demo={showingDemoMetrics}
        />
      </div>

      {/* Prompts table */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-5 h-5 text-amber-500" />
          <h3 className="font-semibold text-slate-700">Prompt Catalog</h3>
        </div>
        {metrics.prompts.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                <th className="text-left px-3 py-2 font-medium">Prompt ID</th>
                <th className="text-right px-3 py-2 font-medium">Version</th>
                <th className="text-right px-3 py-2 font-medium">Calls</th>
              </tr>
            </thead>
            <tbody>
              {metrics.prompts.map(p => (
                <tr key={p.id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-mono text-slate-700">{p.id}</td>
                  <td className="px-3 py-2 text-right text-slate-500">v{p.version}</td>
                  <td className="px-3 py-2 text-right font-mono text-slate-700">{p.calls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-400 italic">
            {health.prompts_loaded
              ? `${health.prompts_loaded} prompts loaded; prompt-level details are not exposed by the live API.`
              : 'Prompt-level details are not exposed by the live API.'}
          </p>
        )}
      </div>

      {/* Eval scores */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Server className="w-5 h-5 text-teal-600" />
          <h3 className="font-semibold text-slate-700">Eval Scores</h3>
          {showingDemoMetrics && (
            <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-600 border border-sky-200">offline / deterministic</span>
          )}
        </div>
        {metrics.eval_scores && Object.keys(metrics.eval_scores).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(metrics.eval_scores).map(([key, score]) => (
              <div key={key}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-mono text-slate-700">{key}</span>
                  <span className={cn(
                    'text-sm font-bold',
                    score >= 0.9 ? 'text-teal-600' : score >= 0.7 ? 'text-amber-600' : 'text-red-600',
                  )}>
                    {(score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      score >= 0.9 ? 'bg-teal-500' : score >= 0.7 ? 'bg-amber-500' : 'bg-red-500',
                    )}
                    style={{ width: `${score * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400 italic">Eval scores are not exposed by the live API.</p>
        )}
      </div>

      {/* Golden rule reminder */}
      <div className="bg-slate-50 rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <Shield className="w-4 h-4 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-600">Guardrails</h3>
        </div>
        <p className="text-sm text-slate-500">LLMs read and explain; deterministic code decides.</p>
        <p className="text-xs text-slate-400 mt-1">Structured output + Pydantic validation + 2 retries + template fallback</p>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color, sub, demo }: {
  icon: React.ComponentType<{ className?: string }>; label: string; value: string; color?: string; sub?: string; demo?: boolean;
}) {
  return (
    <div className={cn('bg-white rounded-lg border p-3', demo ? 'border-sky-200 bg-sky-50/30' : 'border-slate-200')}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className={cn('text-2xl font-bold', color ?? 'text-slate-800')}>
        {value}{demo && <span className="text-xs font-normal text-sky-500 ml-1">(demo)</span>}
      </p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-slate-500 text-xs">{label}</span>
      <p className="font-medium text-slate-700">{value}</p>
    </div>
  );
}
