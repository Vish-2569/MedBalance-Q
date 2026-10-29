import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageSquare, X, Brain, Send, ChevronDown, ChevronRight, Globe, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CopilotMessage } from '@/types/domain';

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';

const SUGGESTED_EN = [
  "Why didn't Hesaraghatta get insulin?",
  'Show cold-chain status',
  'Compare policies',
];
const SUGGESTED_KN = [
  'ಈ ಯೋಜನೆಯ ಸಾರಾಂಶ ಏನು?',
  'ಯಾವ ಔಷಧಿಗಳ ಕೊರತೆ ಉಳಿದಿದೆ?',
  'ಶೀತ ಸರಪಳಿ ಸ್ಥಿತಿ ತೋರಿಸಿ',
];

const FIXTURE_RESPONSES: Record<string, { content: string; tool_calls?: CopilotMessage['tool_calls'] }> = {
  hesaraghatta: {
    content: 'Hesaraghatta (H3) didn\'t receive insulin because:\n\n1. H3 does not have cold storage (cold_storage=false)\n2. Feasibility rule F3 requires cold route + cold vehicle + destination cold storage\n3. Since F3 fails, insulin cannot be transferred to H3\n\nH2 (General Hospital) received the insulin instead — it has cold storage and a cold-capable route from W0.',
    tool_calls: [
      { name: 'check_feasibility', args: { src: 'W0', dst: 'H3', drug: 'INSUL' }, result: { feasible: false, failed_rule: 'F3', reason: 'H3 has no cold storage' } },
    ],
  },
  insulin: {
    content: 'Insulin was routed to H2 instead of H1 because:\n\n1. H2 has zero insulin stock (complete stockout)\n2. H1 still has 10 units effective stock\n3. H2\'s VEN-weighted shortage score (π=3 × 15 units) = 45 outranked H1\'s score (π=3 × 8) = 24\n4. Both have cold-capable routes from W0\n\nThe QUBO optimizer maximizes weighted shortage reduction, so H2 won.',
    tool_calls: [
      { name: 'check_feasibility', args: { src: 'W0', dst: 'H2', drug: 'INSUL' }, result: { feasible: true, rules_passed: ['F1', 'F2', 'F3', 'F4', 'F5'] } },
      { name: 'get_positions', args: { facility: 'H2', drug: 'INSUL' }, result: { effective_stock: 0, shortage: 15 } },
    ],
  },
  cold: {
    content: 'Cold chain status:\n\n• sensor-01 (V1): 4.2°C — OK ✓\n• sensor-02 (V1): 5.1°C — OK ✓\n• sensor-03 (V2): 9.8°C — EXCURSION ⚠️\n\nSensor-03 has been in excursion for ~35 minutes. Any lots in transit via V2 should be quarantined on arrival.',
    tool_calls: [{ name: 'get_coldchain', args: {}, result: { devices: 3, excursions: 1 } }],
  },
  compare: {
    content: 'Policy comparison across solvers:\n\n| Solver | Shortage ↓ | Expiry Saved | Cost |\n|---|---|---|---|\n| No transfer | 0% | ₹0 | ₹0 |\n| Phone-call | 45% | ₹850 | ₹750 |\n| Greedy F4 | 62% | ₹1,420 | ₹980 |\n| QUBO | 72% | ₹1,890 | ₹1,250 |\n| MILP optimal | 74% | ₹1,950 | ₹1,250 |\n\nQUBO achieves 97% of MILP optimality at a fraction of the compute.',
    tool_calls: [{ name: 'get_benchmark', args: {}, result: { solvers: 5, gap_pct: 3.02 } }],
  },
  shortage: {
    content: 'After the current plan, 3 facility-drug pairs still have shortages:\n\n• H1 PARA500: 80 units short (partially addressed)\n• H2 INSUL: 15 units short (28 vials proposed)\n• H3 AMOX500: 120 units short (transfer proposed)\n\nThe plan achieves 72% overall shortage reduction.',
    tool_calls: [{ name: 'get_positions', args: { filter: 'shortage > 0' }, result: { count: 3, total_shortage: 215 } }],
  },
  ಯೋಜನೆ: {
    content: 'ಯೋಜನೆಯ ಸಾರಾಂಶ:\n\n• 6 ವರ್ಗಾವಣೆ ಆದೇಶಗಳು ರಚಿಸಲಾಗಿದೆ\n• 72% ಕೊರತೆ ಕಡಿತ\n• 215 ಘಟಕಗಳ ಮುಕ್ತಾಯ ತಪ್ಪಿಸಲಾಗಿದೆ\n• ₹1,250 ಒಟ್ಟು ಸಾರಿಗೆ ವೆಚ್ಚ',
  },
  ಕೊರತೆ: {
    content: 'ಉಳಿದಿರುವ ಕೊರತೆಗಳು:\n\n• H1 PARA500: 80 ಘಟಕಗಳು\n• H2 INSUL: 15 ಘಟಕಗಳು\n• H3 AMOX500: 120 ಘಟಕಗಳು',
  },
  ಶೀತ: {
    content: 'ಶೀತ ಸರಪಳಿ ಸ್ಥಿತಿ:\n\n• sensor-01: 4.2°C — ಸರಿ ✓\n• sensor-02: 5.1°C — ಸರಿ ✓\n• sensor-03: 9.8°C — ಉಲ್ಲಂಘನೆ ⚠️',
  },
};

function getFixtureResponse(input: string): { content: string; tool_calls?: CopilotMessage['tool_calls'] } {
  const lower = input.toLowerCase();
  for (const [key, resp] of Object.entries(FIXTURE_RESPONSES)) {
    if (lower.includes(key)) return resp;
  }
  return { content: 'I can help with questions about the redistribution plan, drug shortages, cold chain status, and more. Try asking about specific facilities or drugs.' };
}

function ToolCallChip({ call }: { call: NonNullable<CopilotMessage['tool_calls']>[number] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors"
      >
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {call.name}
      </button>
      {open && (
        <div className="mt-1 ml-2 text-xs font-mono bg-slate-50 rounded border border-slate-200 p-2 max-w-full overflow-x-auto">
          <div className="text-slate-500 mb-1">args:</div>
          <pre className="text-slate-700">{JSON.stringify(call.args, null, 2)}</pre>
          {call.result !== undefined && (
            <>
              <div className="text-slate-500 mt-2 mb-1">result:</div>
              <pre className="text-teal-700">{JSON.stringify(call.result, null, 2)}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function CopilotPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [language, setLanguage] = useState<'en' | 'kn'>('en');
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState('');
  const [responding, setResponding] = useState(false);
  const [streamContent, setStreamContent] = useState('');
  const [streamTools, setStreamTools] = useState<NonNullable<CopilotMessage['tool_calls']>>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamContent]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const streamFromSSE = useCallback(async (msg: string) => {
    setResponding(true);
    setStreamContent('');
    setStreamTools([]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch('/api/genai/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, language, user_id: 'web-user' }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) throw new Error(`SSE failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';
      const tools: NonNullable<CopilotMessage['tool_calls']> = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') break;

          try {
            const evt = JSON.parse(payload);
            if (evt.type === 'token' || evt.content) {
              accumulated += evt.content ?? evt.token ?? '';
              setStreamContent(accumulated);
            } else if (evt.type === 'tool_call') {
              tools.push({ name: evt.name, args: evt.args ?? {}, result: evt.result });
              setStreamTools([...tools]);
            }
          } catch {
            // skip malformed JSON lines
          }
        }
      }

      const assistantMsg: CopilotMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: accumulated || 'No response received.',
        tool_calls: tools.length > 0 ? tools : undefined,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const errorMsg: CopilotMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Connection error. The copilot service may be unavailable.',
          timestamp: Date.now(),
        };
        setMessages(prev => [...prev, errorMsg]);
      }
    } finally {
      setStreamContent('');
      setStreamTools([]);
      setResponding(false);
      abortRef.current = null;
    }
  }, [language]);

  const fixtureRespond = useCallback((msg: string) => {
    setResponding(true);
    const resp = getFixtureResponse(msg);

    let charIdx = 0;
    const interval = setInterval(() => {
      charIdx += 3;
      if (charIdx >= resp.content.length) {
        clearInterval(interval);
        setStreamContent('');
        const assistantMsg: CopilotMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: resp.content,
          tool_calls: resp.tool_calls,
          timestamp: Date.now(),
        };
        setMessages(prev => [...prev, assistantMsg]);
        setResponding(false);
      } else {
        setStreamContent(resp.content.slice(0, charIdx));
      }
    }, 15);
  }, []);

  function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || responding) return;

    const userMsg: CopilotMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: msg,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    if (USE_FIXTURES) {
      fixtureRespond(msg);
    } else {
      void streamFromSSE(msg);
    }
  }

  const suggested = language === 'kn' ? SUGGESTED_KN : SUGGESTED_EN;

  return (
    <>
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-teal-600 text-white shadow-lg hover:bg-teal-700 transition-colors flex items-center justify-center"
          title="Open Copilot"
        >
          <MessageSquare className="w-5 h-5" />
        </button>
      )}

      <div
        className={cn(
          'fixed top-0 right-0 bottom-0 w-80 bg-white border-l border-slate-200 z-40 flex flex-col shadow-xl transition-transform duration-200',
          isOpen ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-3 py-2.5 border-b border-slate-200 shrink-0">
          <Brain className="w-4 h-4 text-teal-600" />
          <span className="font-semibold text-slate-700 text-sm flex-1">Copilot</span>
          <button
            onClick={() => setLanguage(l => l === 'en' ? 'kn' : 'en')}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border transition-colors',
              language === 'kn'
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-slate-50 border-slate-200 text-slate-600',
            )}
            title="Toggle language"
          >
            <Globe className="w-3 h-3" />
            {language === 'en' ? 'EN' : 'ಕನ್ನಡ'}
          </button>
          <button onClick={() => setIsOpen(false)} className="p-1 rounded hover:bg-slate-100">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {messages.length === 0 && !streamContent && (
            <div className="text-center text-slate-400 text-xs mt-8">
              <Brain className="w-8 h-8 mx-auto mb-2 opacity-40" />
              <p>{language === 'en' ? 'Ask about the redistribution plan, shortages, or cold chain.' : 'ಪುನರ್ವಿತರಣೆ ಯೋಜನೆ, ಕೊರತೆಗಳು, ಅಥವಾ ಶೀತ ಸರಪಳಿ ಬಗ್ಗೆ ಕೇಳಿ.'}</p>
            </div>
          )}

          {messages.map(m => (
            <div key={m.id} className={cn('flex flex-col', m.role === 'user' ? 'items-end' : 'items-start')}>
              <div
                className={cn(
                  'max-w-[90%] rounded-lg px-3 py-2 text-sm',
                  m.role === 'user'
                    ? 'bg-teal-600 text-white'
                    : 'bg-slate-100 text-slate-800',
                )}
              >
                <p className="whitespace-pre-wrap">{m.content}</p>
              </div>
              {m.tool_calls && m.tool_calls.length > 0 && (
                <div className="max-w-[90%] mt-1 space-y-0.5">
                  {m.tool_calls.map((tc, i) => (
                    <ToolCallChip key={i} call={tc} />
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Streaming content */}
          {responding && streamContent && (
            <div className="flex flex-col items-start">
              <div className="max-w-[90%] bg-slate-100 rounded-lg px-3 py-2 text-sm text-slate-800">
                <p className="whitespace-pre-wrap">{streamContent}</p>
              </div>
              {streamTools.length > 0 && (
                <div className="max-w-[90%] mt-1 space-y-0.5">
                  {streamTools.map((tc, i) => (
                    <ToolCallChip key={i} call={tc} />
                  ))}
                </div>
              )}
            </div>
          )}

          {responding && !streamContent && (
            <div className="flex items-start">
              <div className="bg-slate-100 rounded-lg px-3 py-2 text-sm text-slate-400 flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Thinking...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Suggested questions */}
        {messages.length === 0 && !responding && (
          <div className="px-3 pb-2 space-y-1.5 shrink-0">
            {suggested.map(q => (
              <button
                key={q}
                onClick={() => handleSend(q)}
                className={cn(
                  'w-full text-left px-2.5 py-1.5 rounded border text-xs transition-colors',
                  'bg-slate-50 border-slate-200 text-slate-600 hover:bg-teal-50 hover:border-teal-200 hover:text-teal-700',
                  language === 'kn' && 'font-kannada',
                )}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-slate-200 p-2 flex gap-2 shrink-0">
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={language === 'en' ? 'Ask a question...' : 'ಪ್ರಶ್ನೆ ಕೇಳಿ...'}
            className={cn(
              'flex-1 px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-teal-400',
              language === 'kn' && 'font-kannada',
            )}
            disabled={responding}
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || responding}
            className="p-1.5 rounded-lg bg-teal-600 text-white disabled:opacity-40 hover:bg-teal-700 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  );
}
