import { Brain, Server, Zap, AlertCircle } from 'lucide-react';

export default function AIHealthPage() {
  return (
    <div className="flex-1 flex flex-col p-4 gap-4 overflow-auto">
      <h1 className="text-xl font-semibold text-slate-800">AI Health</h1>

      <div className="grid grid-cols-2 gap-4 max-w-2xl">
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Brain className="w-5 h-5 text-teal-600" />
            <h3 className="font-semibold text-slate-700">GenAI Gateway</h3>
          </div>
          <div className="space-y-2 text-sm">
            <Row label="Provider" value="Gemini" />
            <Row label="Fast Model" value="gemini-2.0-flash" />
            <Row label="Smart Model" value="gemini-2.0-pro" />
            <Row label="Status" value="Healthy" green />
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Server className="w-5 h-5 text-teal-600" />
            <h3 className="font-semibold text-slate-700">Cache</h3>
          </div>
          <div className="space-y-2 text-sm">
            <Row label="Mode" value="DEMO_MODE=live" />
            <Row label="Backend" value="Redis" />
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-5 h-5 text-amber-500" />
            <h3 className="font-semibold text-slate-700">Prompts</h3>
          </div>
          <div className="space-y-2 text-sm">
            <Row label="extract_stock" value="v1" />
            <Row label="anomaly_explain" value="v1" />
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertCircle className="w-5 h-5 text-slate-400" />
            <h3 className="font-semibold text-slate-700">Guardrails</h3>
          </div>
          <div className="space-y-2 text-sm text-slate-600">
            <p>LLMs read and explain; deterministic code decides.</p>
            <p className="text-xs text-slate-400">Structured output + Pydantic validation + 2 retries + template fallback</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, green }: { label: string; value: string; green?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{label}</span>
      <span className={green ? 'text-teal-600 font-medium' : 'text-slate-700 font-medium'}>{value}</span>
    </div>
  );
}
