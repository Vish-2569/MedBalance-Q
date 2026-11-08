import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  MessageSquare, X, Brain, Send, ChevronDown, ChevronRight,
  Globe, Loader2, RotateCcw, Trash2, Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getToken } from '@/lib/auth';
import type { CopilotMessage } from '@/types/domain';

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';

/* ── Suggested questions ──────────────────────────────────────────── */

const SUGGESTED_EN = [
  { label: "Why didn't Hesaraghatta get insulin?", icon: '💊' },
  { label: 'Show cold-chain status', icon: '🌡️' },
  { label: 'Compare policies', icon: '📊' },
  { label: 'Show district overview', icon: '🏥' },
];
const SUGGESTED_KN = [
  { label: 'ಈ ಯೋಜನೆಯ ಸಾರಾಂಶ ಏನು?', icon: '📋' },
  { label: 'ಯಾವ ಔಷಧಿಗಳ ಕೊರತೆ ಉಳಿದಿದೆ?', icon: '💊' },
  { label: 'ಶೀತ ಸರಪಳಿ ಸ್ಥಿತಿ ತೋರಿಸಿ', icon: '🌡️' },
];

/* ── Fixture responses ────────────────────────────────────────────── */

const FIXTURE_RESPONSES: Record<string, { content: string; tool_calls?: CopilotMessage['tool_calls'] }> = {
  hesaraghatta: {
    content: "Hesaraghatta (H3) didn't receive insulin because:\n\n1. **H3 does not have cold storage** (`cold_storage=false`)\n2. Feasibility rule **F3** requires cold route + cold vehicle + destination cold storage\n3. Since F3 fails, insulin cannot be transferred to H3\n\nH2 (General Hospital) received the insulin instead — it has cold storage and a cold-capable route from W0.",
    tool_calls: [
      { name: 'why_not', args: { facility: 'H3', drug: 'INSUL' }, result: { facility_id: 'H3', drug_code: 'INSUL', residual_shortage: 15, candidates: [{ src: 'W0', feasible: false, failed_rules: ['F3'], reason: 'H3 has no cold storage' }] } },
    ],
  },
  insulin: {
    content: "Insulin was routed to **H2** instead of H1 because:\n\n1. H2 has **zero** insulin stock (complete stockout)\n2. H1 still has 10 units effective stock\n3. H2's VEN-weighted shortage score outranked H1's\n4. Both have cold-capable routes from W0\n\nThe optimizer maximizes weighted shortage reduction, so H2 won.",
    tool_calls: [
      { name: 'why_not', args: { facility: 'H1', drug: 'INSUL' }, result: { facility_id: 'H1', drug_code: 'INSUL', residual_shortage: 8, candidates: [{ src: 'W0', feasible: true, net_score: 0.72 }] } },
      { name: 'get_stock_position', args: { facility: 'H2', drug: 'INSUL' }, result: { facility_id: 'H2', drug_code: 'INSUL', effective_stock: 0, shortage: 15, at_risk: 0, reserve: 0 } },
    ],
  },
  cold: {
    content: "**Cold chain status:**\n\n| Sensor | Vehicle | Temp | Status |\n|---|---|---|---|\n| sensor-01 | V1 | 4.2°C | OK |\n| sensor-02 | V1 | 5.1°C | OK |\n| sensor-03 | V2 | 9.8°C | EXCURSION |\n\nSensor-03 has been in excursion for ~35 minutes. Any lots in transit via V2 should be quarantined on arrival.",
    tool_calls: [{ name: 'get_coldchain_status', args: {}, result: { devices: [{ device_id: 'sensor-01', state: 'ok' }, { device_id: 'sensor-02', state: 'ok' }, { device_id: 'sensor-03', state: 'excursion' }] } }],
  },
  compare: {
    content: "**Policy comparison** from 28-day replay (20 seeds):\n\n| Solver | Stockout Reduction | Waste Moved | Cost |\n|---|---|---|---|\n| No transfer | 0% | 0 | ₹0 |\n| QUBO (qpiai-local) | 52% | 45,360 | ₹80,354 |\n| Greedy F4 | 86% | 8,437 | ₹57,605 |\n| Phone-call greedy | 89% | 8,478 | ₹58,005 |\n\nGreedy baselines outperform QUBO on stockout reduction. QUBO moves 5x more at-risk stock as a multi-objective trade-off.",
    tool_calls: [{ name: 'compare_policies', args: {}, result: { policies: [{ facility_id: 'H1', drug_code: 'INSUL', min_reserve_days: 7, target_days: 14 }] } }],
  },
  shortage: {
    content: "After the current plan, **3 facility-drug pairs** still have shortages:\n\n| Facility | Drug | Shortage |\n|---|---|---|\n| H1 | PARA500 | 80 units |\n| H2 | INSUL | 15 units |\n| H3 | AMOX500 | 120 units |\n\nH2's insulin shortage is partially addressed with 28 vials proposed.",
    tool_calls: [{ name: 'get_stock_position', args: { facility: 'H1', drug: 'PARA500' }, result: { facility_id: 'H1', drug_code: 'PARA500', effective_stock: 120, shortage: 80, at_risk: 0, reserve: 50 } }],
  },
  overview: {
    content: "**District overview:**\n\n| Facility | Type | Cold Storage |\n|---|---|---|\n| W0 — District Warehouse | Warehouse | Yes |\n| H1 — City Hospital | Hospital | Yes |\n| H2 — General Hospital | Hospital | Yes |\n| H3 — Community Health Centre | Hospital | No |\n| H4 — Primary Health Centre | Hospital | No |\n\n**Summary:** 9 stock positions tracked, total shortage **493 units**, at-risk stock **65 units** across 4 drug types.",
    tool_calls: [{ name: 'get_district_overview', args: {}, result: { facilities: [{ id: 'W0' }, { id: 'H1' }, { id: 'H2' }, { id: 'H3' }, { id: 'H4' }], total_shortage: 493, total_at_risk: 65 } }],
  },
  district: {
    content: "**District overview:**\n\n| Facility | Type | Cold Storage |\n|---|---|---|\n| W0 — District Warehouse | Warehouse | Yes |\n| H1 — City Hospital | Hospital | Yes |\n| H2 — General Hospital | Hospital | Yes |\n| H3 — Community Health Centre | Hospital | No |\n| H4 — Primary Health Centre | Hospital | No |\n\n**Summary:** 9 stock positions tracked, total shortage **493 units**, at-risk stock **65 units**.",
    tool_calls: [{ name: 'get_district_overview', args: {}, result: { facilities: [{ id: 'W0' }, { id: 'H1' }, { id: 'H2' }, { id: 'H3' }, { id: 'H4' }], total_shortage: 493, total_at_risk: 65 } }],
  },
  order: {
    content: "**Order ORD-001:**\n\n| Field | Value |\n|---|---|\n| DTA | DTA/BLR-U/2026/000001 |\n| Drug | Paracetamol 500mg |\n| Qty | 180 units |\n| From | W0 (District Warehouse) |\n| To | H2 (General Hospital) |\n| Status | Proposed |\n| Temperature | Ambient |\n| Score | 0.92 |",
    tool_calls: [{ name: 'explain_order', args: { order_id: 'ORD-001' }, result: { order: { id: 'ORD-001', drug_name: 'Paracetamol 500mg', qty: 180, status: 'proposed' } } }],
  },
  paracetamol: {
    content: "**Paracetamol 500mg stock across facilities:**\n\n| Facility | Effective Stock | Shortage | At-Risk | Reserve |\n|---|---|---|---|---|\n| W0 | 2,000 | 0 | 0 | 200 |\n| H1 | 100 | 80 | 50 | 60 |\n| H2 | 50 | 130 | 0 | 60 |\n| H4 | 80 | 40 | 0 | 30 |\n\nH2 has the highest shortage (130 units). Order ORD-001 proposes transferring 180 units from W0 to H2.",
    tool_calls: [{ name: 'get_stock_position', args: { facility: 'H2', drug: 'PARA500' }, result: { facility_id: 'H2', drug_code: 'PARA500', effective_stock: 50, shortage: 130, at_risk: 0, reserve: 60 } }],
  },
  audit: {
    content: "**Audit trail for ORD-001:**\n\n| # | Actor | Action | Timestamp |\n|---|---|---|---|\n| 1 | optimizer | propose | 2026-11-01 10:30:01 |\n\nThe order was proposed by the optimizer as part of the redistribution plan. No further state changes yet (still in *proposed* status).",
    tool_calls: [{ name: 'get_audit_trail', args: { order_id: 'ORD-001' }, result: { order_id: 'ORD-001', entries: [{ seq: 2, actor: 'optimizer', action: 'propose' }] } }],
  },
  'what if': {
    content: "**What-if: Repair H4 cold storage**\n\n| Metric | Baseline | Scenario | Delta |\n|---|---|---|---|\n| Shortage reduction | 72% | 85% | +13% |\n| Expiry avoided | 215 units | 243 units | +28 |\n| Cost | ₹1,250 | ₹1,420 | +₹170 |\n| Trips | 6 | 7 | +1 |\n\nRepairing H4's cold storage would enable insulin delivery to H4, adding 1 new order (28 vials INSUL → H4).",
    tool_calls: [{ name: 'what_if', args: { overrides: [{ action: 'repair_cold_storage', facility: 'H4' }] }, result: { diff: { shortage_reduction_delta: 0.13, orders_added: [{ dst_facility_id: 'H4', drug_code: 'INSUL', qty: 28 }] } } }],
  },
  help: {
    content: "I can help with:\n\n- **Stock queries** — \"Show H1 PARA500 position\", \"District overview\"\n- **Order details** — \"Explain ORD-001\", \"Audit trail for ORD-005\"\n- **Why-not analysis** — \"Why didn't H3 get insulin?\"\n- **Cold chain** — \"Show cold-chain status\"\n- **What-if scenarios** — \"What if we repair H4 cold storage?\"\n- **Policy comparison** — \"Compare policies across facilities\"\n\nTry one of the suggested questions below, or ask anything about the redistribution plan!",
  },
  ಯೋಜನೆ: {
    content: '**ಯೋಜನೆಯ ಸಾರಾಂಶ:**\n\n- 6 ವರ್ಗಾವಣೆ ಆದೇಶಗಳು ರಚಿಸಲಾಗಿದೆ\n- **52%** ಕೊರತೆ ಕಡಿತ (QUBO ನೀತಿ)\n- 45,360 ಘಟಕಗಳ ಅಪಾಯದಲ್ಲಿರುವ ದಾಸ್ತಾನು ಸ್ಥಳಾಂತರ\n- ₹80,354 ಒಟ್ಟು ಸಾರಿಗೆ ವೆಚ್ಚ',
  },
  ಕೊರತೆ: {
    content: '**ಉಳಿದಿರುವ ಕೊರತೆಗಳು:**\n\n| ಸೌಲಭ್ಯ | ಔಷಧ | ಕೊರತೆ |\n|---|---|---|\n| H1 | PARA500 | 80 ಘಟಕಗಳು |\n| H2 | INSUL | 15 ಘಟಕಗಳು |\n| H3 | AMOX500 | 120 ಘಟಕಗಳು |',
  },
  ಶೀತ: {
    content: '**ಶೀತ ಸರಪಳಿ ಸ್ಥಿತಿ:**\n\n| ಸಂವೇದಕ | ವಾಹನ | ತಾಪಮಾನ | ಸ್ಥಿತಿ |\n|---|---|---|---|\n| sensor-01 | V1 | 4.2°C | ಸರಿ |\n| sensor-02 | V1 | 5.1°C | ಸರಿ |\n| sensor-03 | V2 | 9.8°C | ಉಲ್ಲಂಘನೆ |',
  },
};

function getFixtureResponse(input: string): { content: string; tool_calls?: CopilotMessage['tool_calls'] } {
  const lower = input.toLowerCase();
  for (const [key, resp] of Object.entries(FIXTURE_RESPONSES)) {
    if (lower.includes(key)) return resp;
  }
  if (lower.includes('h1') || lower.includes('h2') || lower.includes('h3') || lower.includes('h4') || lower.includes('w0'))
    return FIXTURE_RESPONSES['overview'];
  return FIXTURE_RESPONSES['help'];
}

/* ── Simple markdown renderer ─────────────────────────────────────── */

function MarkdownContent({ text }: { text: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return <div className="space-y-2">{blocks}</div>;
}

function parseMarkdown(text: string) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.match(/^\|.*\|/) && i + 1 < lines.length && lines[i + 1].match(/^\|[\s\-:|]+\|/)) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].match(/^\|.*\|/)) {
        tableLines.push(lines[i]);
        i++;
      }
      elements.push(<MarkdownTable key={key++} lines={tableLines} />);
      continue;
    }

    if (line.match(/^#{1,3}\s/)) {
      const level = (line.match(/^#+/) as RegExpMatchArray)[0].length;
      const content = line.replace(/^#+\s+/, '');
      const Tag = `h${level}` as keyof JSX.IntrinsicElements;
      const cls = level === 1 ? 'text-sm font-bold' : level === 2 ? 'text-sm font-semibold' : 'text-xs font-semibold';
      elements.push(<Tag key={key++} className={cls}>{inlineMarkdown(content)}</Tag>);
      i++;
      continue;
    }

    if (line.match(/^[-*•]\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^[-*•]\s/)) {
        listItems.push(lines[i].replace(/^[-*•]\s+/, ''));
        i++;
      }
      elements.push(
        <ul key={key++} className="list-disc list-inside space-y-0.5">
          {listItems.map((item, j) => <li key={j} className="text-sm">{inlineMarkdown(item)}</li>)}
        </ul>,
      );
      continue;
    }

    if (line.match(/^\d+\.\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        listItems.push(lines[i].replace(/^\d+\.\s+/, ''));
        i++;
      }
      elements.push(
        <ol key={key++} className="list-decimal list-inside space-y-0.5">
          {listItems.map((item, j) => <li key={j} className="text-sm">{inlineMarkdown(item)}</li>)}
        </ol>,
      );
      continue;
    }

    if (line.trim() === '') {
      i++;
      continue;
    }

    elements.push(<p key={key++} className="text-sm">{inlineMarkdown(line)}</p>);
    i++;
  }

  return elements;
}

function inlineMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    const codeMatch = remaining.match(/`([^`]+)`/);

    let earliest: { type: 'bold' | 'code'; index: number; match: RegExpMatchArray } | null = null;

    if (boldMatch && boldMatch.index !== undefined) {
      earliest = { type: 'bold', index: boldMatch.index, match: boldMatch };
    }
    if (codeMatch && codeMatch.index !== undefined) {
      if (!earliest || codeMatch.index < earliest.index) {
        earliest = { type: 'code', index: codeMatch.index, match: codeMatch };
      }
    }

    if (!earliest) {
      parts.push(remaining);
      break;
    }

    if (earliest.index > 0) {
      parts.push(remaining.slice(0, earliest.index));
    }

    if (earliest.type === 'bold') {
      parts.push(<strong key={key++} className="font-semibold">{earliest.match[1]}</strong>);
    } else {
      parts.push(
        <code key={key++} className="px-1 py-0.5 rounded bg-slate-200 text-xs font-mono">
          {earliest.match[1]}
        </code>,
      );
    }

    remaining = remaining.slice(earliest.index + earliest.match[0].length);
  }

  return parts;
}

function MarkdownTable({ lines }: { lines: string[] }) {
  const parseRow = (line: string) =>
    line.split('|').slice(1, -1).map(cell => cell.trim());

  const headers = parseRow(lines[0]);
  const rows = lines.slice(2).map(parseRow);

  return (
    <div className="overflow-x-auto rounded border border-slate-200">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {headers.map((h, i) => (
              <th key={i} className="px-2 py-1.5 text-left font-semibold text-slate-600 whitespace-nowrap">
                {inlineMarkdown(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}>
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1 text-slate-700 whitespace-nowrap">
                  {inlineMarkdown(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Tool call chip ───────────────────────────────────────────────── */

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

/* ── Main panel ───────────────────────────────────────────────────── */

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
  const sessionIdRef = useRef(crypto.randomUUID());
  const fixtureIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamContent]);

  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isOpen]);

  useEffect(() => {
    return () => {
      if (fixtureIntervalRef.current) clearInterval(fixtureIntervalRef.current);
    };
  }, []);

  const streamFromSSE = useCallback(async (msg: string) => {
    setResponding(true);
    setStreamContent('');
    setStreamTools([]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = getToken();
      const res = await fetch('/api/genai/copilot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: msg, language, user_id: 'web-user', session_id: sessionIdRef.current }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`Copilot API returned HTTP ${res.status}.`);
      if (!res.body) throw new Error('Copilot API returned an empty stream.');

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';
      let answerText = '';
      let responseError = '';
      const tools: NonNullable<CopilotMessage['tool_calls']> = [];

      let answerModel = '';
      let answerPromptId = '';

      const processFrame = (frame: string) => {
        const payload = frame
          .split('\n')
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).replace(/^ /, ''))
          .join('\n')
          .trim();
        if (!payload || payload === '[DONE]') return;

        const evt = JSON.parse(payload);
        const eventText = [evt.text, evt.content, evt.token]
          .find(value => typeof value === 'string') as string | undefined;

        if (evt.type === 'token') {
          if (eventText) {
            accumulated += eventText;
            setStreamContent(accumulated);
          }
        } else if (evt.type === 'answer') {
          answerText = eventText ?? '';
          if (evt.model) answerModel = evt.model;
          if (evt.prompt_id) answerPromptId = evt.prompt_id;
          setStreamContent(answerText);
        } else if (evt.type === 'error') {
          responseError = eventText || 'The copilot could not generate a response.';
        } else if (evt.type === 'tool_call') {
          tools.push({ name: evt.name, args: evt.args ?? {}, result: evt.result });
          setStreamTools([...tools]);
        } else if (evt.type === 'tool_result') {
          const toolIndex = tools.map(tool => tool.name).lastIndexOf(evt.name);
          if (toolIndex >= 0) {
            tools[toolIndex] = { ...tools[toolIndex], result: evt.result ?? evt.summary };
            setStreamTools([...tools]);
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.replace(/\r\n/g, '\n').split('\n\n');
        buffer = frames.pop() ?? '';
        frames.forEach(processFrame);
      }

      buffer += decoder.decode();
      if (buffer.trim()) processFrame(buffer.replace(/\r\n/g, '\n'));

      const assistantMsg: CopilotMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: responseError
          ? `Copilot error: ${responseError}`
          : (answerText || accumulated).trim() || 'The copilot returned an empty response.',
        tool_calls: tools.length > 0 ? tools : undefined,
        timestamp: Date.now(),
        model: answerModel || undefined,
        prompt_id: answerPromptId || undefined,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const errorMsg: CopilotMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Copilot request failed: ${(err as Error).message}`,
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
      charIdx += 5;
      if (charIdx >= resp.content.length) {
        clearInterval(interval);
        fixtureIntervalRef.current = null;
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
    }, 12);
    fixtureIntervalRef.current = interval;
  }, []);

  const MAX_MSG = 2000;

  function handleSend(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || responding) return;
    if (msg.length > MAX_MSG) return;

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

  function handleRetry(messageIndex: number) {
    const userMsgIdx = messageIndex - 1;
    if (userMsgIdx < 0 || messages[userMsgIdx]?.role !== 'user') return;
    const userText = messages[userMsgIdx].content;
    setMessages(prev => prev.slice(0, userMsgIdx));
    handleSend(userText);
  }

  function handleClear() {
    if (responding && abortRef.current) abortRef.current.abort();
    setMessages([]);
    setStreamContent('');
    setStreamTools([]);
    setResponding(false);
    sessionIdRef.current = crypto.randomUUID();
  }

  const suggested = language === 'kn' ? SUGGESTED_KN : SUGGESTED_EN;
  const isError = (m: CopilotMessage) =>
    m.role === 'assistant' && (m.content.startsWith('Copilot error:') || m.content.startsWith('Copilot request failed:') || m.content.includes('Demo fallback'));

  return (
    <>
      {/* FAB */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-[1100] w-14 h-14 rounded-full bg-teal-600 text-white shadow-lg hover:bg-teal-700 hover:scale-105 transition-all flex items-center justify-center group"
          title="Open Copilot"
        >
          <MessageSquare className="w-5 h-5 group-hover:hidden" />
          <Sparkles className="w-5 h-5 hidden group-hover:block" />
        </button>
      )}

      {/* Panel */}
      <div
        className={cn(
          'copilot-panel fixed top-0 right-0 bottom-0 bg-white border-l border-slate-200 z-[1100] flex flex-col shadow-xl transition-transform duration-200',
          isOpen ? 'translate-x-0' : 'translate-x-full',
        )}
        style={{ width: 420 }}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 shrink-0 bg-gradient-to-r from-teal-50 to-white">
          <Brain className="w-5 h-5 text-teal-600" />
          <span className="font-semibold text-slate-800 flex-1">MedBalance Copilot</span>
          <button
            onClick={() => setLanguage(l => l === 'en' ? 'kn' : 'en')}
            className={cn(
              'flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border transition-colors',
              language === 'kn'
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100',
            )}
            title="Toggle language"
          >
            <Globe className="w-3 h-3" />
            {language === 'en' ? 'EN' : 'ಕನ್ನಡ'}
          </button>
          {messages.length > 0 && (
            <button
              onClick={handleClear}
              className="p-1.5 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
              title="Clear conversation"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          <button onClick={() => setIsOpen(false)} className="p-1.5 rounded-md hover:bg-slate-100 transition-colors">
            <X className="w-4 h-4 text-slate-500" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
          {/* Welcome state */}
          {messages.length === 0 && !streamContent && (
            <div className="text-center mt-6 mb-4">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-teal-50 flex items-center justify-center">
                <Brain className="w-6 h-6 text-teal-600" />
              </div>
              <h3 className="font-semibold text-slate-700 text-sm mb-1">
                {language === 'en' ? 'District Drug Officer Copilot' : 'ಜಿಲ್ಲಾ ಔಷಧ ಅಧಿಕಾರಿ ಸಹಾಯಕ'}
              </h3>
              <p className="text-xs text-slate-500 max-w-[280px] mx-auto">
                {language === 'en'
                  ? 'Ask about stock positions, transfer orders, shortages, cold chain, or run what-if scenarios.'
                  : 'ದಾಸ್ತಾನು ಸ್ಥಾನಗಳು, ವರ್ಗಾವಣೆ ಆದೇಶಗಳು, ಕೊರತೆಗಳು ಅಥವಾ ಶೀತ ಸರಪಳಿ ಬಗ್ಗೆ ಕೇಳಿ.'}
              </p>
            </div>
          )}

          {messages.map((m, idx) => (
            <div key={m.id} className={cn('flex flex-col', m.role === 'user' ? 'items-end' : 'items-start')}>
              <div
                className={cn(
                  'max-w-[95%] rounded-xl px-3.5 py-2.5',
                  m.role === 'user'
                    ? 'bg-teal-600 text-white'
                    : isError(m)
                      ? 'bg-amber-50 border border-amber-200 text-slate-800'
                      : 'bg-slate-50 border border-slate-200 text-slate-800',
                )}
              >
                {m.role === 'user' ? (
                  <p className="text-sm whitespace-pre-wrap">{m.content}</p>
                ) : (
                  <MarkdownContent text={m.content} />
                )}
              </div>

              {/* Tool calls */}
              {m.tool_calls && m.tool_calls.length > 0 && (
                <div className="max-w-[95%] mt-1 space-y-0.5">
                  {m.tool_calls.map((tc, i) => (
                    <ToolCallChip key={i} call={tc} />
                  ))}
                </div>
              )}

              {/* Model info */}
              {m.role === 'assistant' && (m.model || m.prompt_id) && (
                <div className="max-w-[95%] mt-0.5 px-1 text-[10px] text-slate-400 select-none">
                  {[m.model, m.prompt_id].filter(Boolean).join(' · ')}
                </div>
              )}

              {/* Retry button on errors */}
              {isError(m) && !responding && (
                <button
                  onClick={() => handleRetry(idx)}
                  className="mt-1 flex items-center gap-1 px-2 py-1 rounded-md text-xs text-amber-700 hover:bg-amber-50 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  Retry
                </button>
              )}
            </div>
          ))}

          {/* Streaming content */}
          {responding && streamContent && (
            <div className="flex flex-col items-start">
              <div className="max-w-[95%] bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5">
                <MarkdownContent text={streamContent} />
              </div>
              {streamTools.length > 0 && (
                <div className="max-w-[95%] mt-1 space-y-0.5">
                  {streamTools.map((tc, i) => (
                    <ToolCallChip key={i} call={tc} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Thinking indicator */}
          {responding && !streamContent && (
            <div className="flex items-start">
              <div className="bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
                <span className="text-sm text-slate-500">Thinking...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Suggested questions */}
        {!responding && (
          <div className="px-3 pb-2 shrink-0">
            <div className="flex flex-wrap gap-1.5">
              {suggested.map(q => (
                <button
                  key={q.label}
                  onClick={() => handleSend(q.label)}
                  className={cn(
                    'px-2.5 py-1.5 rounded-full border text-xs transition-colors',
                    'bg-white border-slate-200 text-slate-600 hover:bg-teal-50 hover:border-teal-300 hover:text-teal-700',
                    language === 'kn' && 'font-kannada',
                  )}
                >
                  <span className="mr-1">{q.icon}</span>
                  {q.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-slate-200 p-3 shrink-0 bg-white">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
              aria-label={language === 'en' ? 'Ask a question' : 'ಪ್ರಶ್ನೆ ಕೇಳಿ'}
              placeholder={language === 'en' ? 'Ask about stock, orders, cold chain...' : 'ದಾಸ್ತಾನು, ಆದೇಶಗಳು, ಶೀತ ಸರಪಳಿ ಬಗ್ಗೆ ಕೇಳಿ...'}
              maxLength={MAX_MSG}
              className={cn(
                'flex-1 px-3.5 py-2 rounded-xl border border-slate-200 text-sm',
                'focus:outline-none focus:ring-2 focus:ring-teal-400 focus:border-transparent',
                'placeholder:text-slate-400',
                language === 'kn' && 'font-kannada',
              )}
              disabled={responding}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || responding}
              className="p-2 rounded-xl bg-teal-600 text-white disabled:opacity-40 hover:bg-teal-700 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
