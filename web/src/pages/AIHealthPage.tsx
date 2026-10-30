import { useQuery } from '@tanstack/react-query';
import {
  Brain, Server, Zap, Shield, AlertCircle, Activity,
  Clock, Database, Loader2, RefreshCw,
} from 'lucide-react';
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
          value={health.total_calls == null ? 'Unavailable' : String(health.total_calls)}
          color="text-teal-600"
        />
        <StatCard
          icon={Database}
          label="Cache Hit Rate"
          value={health.cache_hit_rate == null ? 'Unavailable' : formatPct(health.cache_hit_rate)}
          color="text-blue-600"
          sub={health.cache_hit_rate == null ? undefined : health.cache_hit_rate >= 0.5 ? 'Good' : 'Low'}
        />
        <StatCard
          icon={Clock}
          label="P95 Latency"
          value={health.p95_latency_ms == null ? 'Unavailable' : `${health.p95_latency_ms}ms`}
          color={health.p95_latency_ms != null && health.p95_latency_ms > 2000 ? 'text-red-600' : 'text-slate-800'}
        />
        <StatCard
          icon={AlertCircle}
          label="Schema Failures"
          value={health.schema_failures == null ? 'Unavailable' : String(health.schema_failures)}
          color={health.schema_failures != null && health.schema_failures > 5 ? 'text-red-600' : 'text-amber-600'}
        />
        <StatCard
          icon={RefreshCw}
          label="Fallbacks"
          value={health.fallbacks == null ? 'Unavailable' : String(health.fallbacks)}
          color="text-amber-600"
          sub="Calls using fallback"
        />
        <StatCard
          icon={Shield}
          label="Firewall Blocks"
          value={health.firewall_blocks == null ? 'Unavailable' : String(health.firewall_blocks)}
          color={health.firewall_blocks != null && health.firewall_blocks > 0 ? 'text-red-600' : 'text-teal-600'}
          sub="Narration grounding"
        />
      </div>

      {/* Prompts table */}
      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-5 h-5 text-amber-500" />
          <h3 className="font-semibold text-slate-700">Prompt Catalog</h3>
        </div>
        {health.prompts.length > 0 ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-xs text-slate-500 uppercase">
                <th className="text-left px-3 py-2 font-medium">Prompt ID</th>
                <th className="text-right px-3 py-2 font-medium">Version</th>
                <th className="text-right px-3 py-2 font-medium">Calls</th>
              </tr>
            </thead>
            <tbody>
              {health.prompts.map(p => (
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
        </div>
        {health.eval_scores && Object.keys(health.eval_scores).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(health.eval_scores).map(([key, score]) => (
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

function StatCard({ icon: Icon, label, value, color, sub }: {
  icon: React.ComponentType<{ className?: string }>; label: string; value: string; color?: string; sub?: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-3">
      <div className="flex items-center gap-2 mb-1">
        <Icon className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-medium">{label}</span>
      </div>
      <p className={cn('text-2xl font-bold', color ?? 'text-slate-800')}>{value}</p>
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
