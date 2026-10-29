import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { SSEEvent } from '@/types/domain';

const MAX_EVENTS = 50;
let globalEvents: SSEEvent[] = [];
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach(l => l());
}

export function useSSEConnection() {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES === '1';
    if (USE_FIXTURES) return;

    const es = new EventSource('/api/core/events');
    esRef.current = es;

    const EVENT_TYPES = [
      'report.received', 'inventory.updated', 'anomaly.flagged',
      'forecast.updated', 'coldchain.alert', 'plan.progress',
      'plan.completed', 'plan.revised', 'order.status', 'custody.scanned',
    ];

    const handler = (type: string) => (e: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(e.data as string); } catch { /* noop */ }

      const evt: SSEEvent = {
        id: crypto.randomUUID(),
        type,
        data,
        timestamp: Date.now(),
      };

      globalEvents = [evt, ...globalEvents].slice(0, MAX_EVENTS);
      notify();

      if (type === 'inventory.updated') {
        void queryClient.invalidateQueries({ queryKey: ['positions'] });
        void queryClient.invalidateQueries({ queryKey: ['lots'] });
      } else if (type === 'plan.completed' || type === 'plan.revised') {
        void queryClient.invalidateQueries({ queryKey: ['plan'] });
        void queryClient.invalidateQueries({ queryKey: ['orders'] });
      } else if (type === 'order.status') {
        void queryClient.invalidateQueries({ queryKey: ['orders'] });
      } else if (type === 'report.received' || type === 'anomaly.flagged') {
        void queryClient.invalidateQueries({ queryKey: ['reports'] });
        void queryClient.invalidateQueries({ queryKey: ['reviews'] });
      } else if (type === 'coldchain.alert') {
        void queryClient.invalidateQueries({ queryKey: ['coldchain'] });
      }
    };

    EVENT_TYPES.forEach(t => es.addEventListener(t, handler(t)));
    es.onerror = () => {
      setTimeout(() => {
        if (esRef.current === es) {
          es.close();
          esRef.current = null;
        }
      }, 5000);
    };

    return () => { es.close(); esRef.current = null; };
  }, [queryClient]);
}

export function useLiveEvents(n = 5): SSEEvent[] {
  const [events, setEvents] = useState<SSEEvent[]>([]);

  useEffect(() => {
    const update = () => setEvents([...globalEvents.slice(0, n)]);
    listeners.add(update);
    update();
    return () => { listeners.delete(update); };
  }, [n]);

  return events;
}
