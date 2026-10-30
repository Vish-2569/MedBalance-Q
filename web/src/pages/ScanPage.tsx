import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Truck, PackageCheck, CheckCircle, AlertTriangle, QrCode, Package, Activity } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, statusColor } from '@/lib/utils';
import type { OrderStatus } from '@/types/domain';

const NEXT_EVENT: Record<string, { event: string; label: string; icon: typeof Truck; color: string }> = {
  approved: { event: 'dispatch', label: 'Dispatch', icon: Truck, color: 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800' },
  dispatched: { event: 'receive', label: 'Receive', icon: PackageCheck, color: 'bg-teal-600 hover:bg-teal-700 active:bg-teal-800' },
  received: { event: 'consume', label: 'Consume', icon: CheckCircle, color: 'bg-green-600 hover:bg-green-700 active:bg-green-800' },
};

export default function ScanPage() {
  const { token } = useParams<{ token: string }>();
  const queryClient = useQueryClient();
  const [receiveQty, setReceiveQty] = useState<string>('');
  const [localStatus, setLocalStatus] = useState<OrderStatus | null>(null);
  const [lastEvent, setLastEvent] = useState<string | null>(null);

  const { data: orders = [], isLoading, isError } = useQuery({
    queryKey: ['orders'],
    queryFn: () => api.getOrders(),
  });

  const order = orders.find(o => {
    if (!token) return false;
    if (o.id === token) return true;
    if (o.dta_number === token) return true;
    return false;
  });

  const currentStatus = localStatus ?? order?.status;

  const scanMut = useMutation({
    mutationFn: (payload: { token: string; event: string; qty?: number; actor: string }) =>
      api.custodyScan(payload),
    onSuccess: (data) => {
      setLocalStatus(data.status as OrderStatus);
      setLastEvent(data.event);
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      void queryClient.invalidateQueries({ queryKey: ['planDemo'] });
    },
  });

  const action = currentStatus ? NEXT_EVENT[currentStatus] : undefined;

  function handleScan() {
    if (!token || !action) return;
    const qty = action.event === 'receive' && receiveQty ? parseInt(receiveQty, 10) : undefined;
    scanMut.mutate({ token, event: action.event, qty, actor: 'mobile-scanner' });
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto" />
          <p className="text-slate-700 font-medium">No scan token provided</p>
          <p className="text-sm text-slate-500">Scan a QR code on a DTA voucher to begin.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-4 border-teal-200 border-t-teal-600 rounded-full animate-spin mx-auto" />
          <p className="text-sm text-slate-500">Loading order...</p>
        </div>
      </div>
    );
  }

  if (isError || !order) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
        <div className="text-center space-y-3">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto" />
          <p className="text-slate-700 font-medium">{isError ? 'Could not load orders' : 'Order not found'}</p>
          <p className="text-sm text-slate-500">
            {isError
              ? 'The core API is unavailable. Try again when it is healthy.'
              : 'No order ID or DTA number matches this token. QR-token lookup is not exposed by the live order API.'}
          </p>
        </div>
      </div>
    );
  }

  const isTerminal = currentStatus === 'consumed' || currentStatus === 'rejected' || currentStatus === 'cancelled';

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center gap-2">
        <Activity className="w-5 h-5 text-teal-600" />
        <span className="font-semibold text-teal-700">MedBalance-Q</span>
        <span className="text-slate-400 text-sm ml-auto">Custody Scan</span>
      </header>

      <div className="flex-1 flex flex-col items-center p-4 max-w-md mx-auto w-full">
        {/* QR Icon */}
        <div className="mt-4 mb-6">
          <div className="w-16 h-16 rounded-2xl bg-teal-50 border-2 border-teal-200 flex items-center justify-center">
            <QrCode className="w-8 h-8 text-teal-600" />
          </div>
        </div>

        {/* Success flash */}
        {lastEvent && (
          <div className="w-full mb-4 p-3 rounded-xl bg-green-50 border border-green-200 flex items-center gap-2">
            <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
            <span className="text-sm text-green-800 font-medium">
              {lastEvent === 'dispatch' ? 'Dispatched' : lastEvent === 'receive' ? 'Received' : 'Consumed'} successfully
            </span>
          </div>
        )}

        {/* Order Summary Card */}
        <div className="w-full bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <span className="text-xs font-mono text-slate-500">{order.dta_number}</span>
            <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', statusColor(currentStatus ?? order.status))}>
              {currentStatus ?? order.status}
            </span>
          </div>

          <div className="p-4 space-y-3">
            <div className="flex items-start gap-3">
              <Package className="w-5 h-5 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold text-slate-800">{order.drug_name}</p>
                <p className="text-sm text-slate-500">{order.qty} {order.drug_code === 'INSUL' ? 'vials' : 'units'} · Batch {order.batch_no}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-sm">
              <span className="px-2 py-1 bg-slate-50 rounded-lg text-slate-700 font-medium">{order.src_facility_id}</span>
              <span className="text-slate-400">→</span>
              <span className="px-2 py-1 bg-slate-50 rounded-lg text-slate-700 font-medium">{order.dst_facility_id}</span>
              {order.temperature_req === 'cold_chain' && (
                <span className="text-xs px-2 py-0.5 bg-blue-50 border border-blue-200 text-blue-700 rounded-full">❄ Cold</span>
              )}
            </div>

            <div className="text-xs text-slate-400">
              Score: {order.score.toFixed(2)} · Plan: {order.plan_id}
            </div>
          </div>
        </div>

        {/* Qty input for receive */}
        {action?.event === 'receive' && (
          <div className="w-full mt-4">
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Received quantity</label>
            <input
              type="number"
              value={receiveQty}
              onChange={e => setReceiveQty(e.target.value)}
              placeholder={String(order.qty)}
              className="w-full h-12 px-4 text-lg rounded-xl border border-slate-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition-colors"
            />
            <p className="text-xs text-slate-400 mt-1">Leave blank to confirm full quantity ({order.qty})</p>
          </div>
        )}

        {/* Action button */}
        {action && !isTerminal && (
          <button
            onClick={handleScan}
            disabled={scanMut.isPending}
            className={cn(
              'w-full mt-6 h-14 rounded-xl text-white font-semibold text-lg flex items-center justify-center gap-3 transition-colors shadow-sm',
              action.color,
              scanMut.isPending && 'opacity-60 cursor-not-allowed',
            )}
          >
            {scanMut.isPending ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <action.icon className="w-6 h-6" />
            )}
            {scanMut.isPending ? 'Processing...' : action.label}
          </button>
        )}

        {/* Terminal state */}
        {isTerminal && (
          <div className="w-full mt-6 p-4 rounded-xl bg-slate-100 text-center">
            <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
            <p className="font-medium text-slate-700">Order {currentStatus}</p>
            <p className="text-sm text-slate-500 mt-1">Custody chain complete. No further actions.</p>
          </div>
        )}

        {/* Error */}
        {scanMut.isError && (
          <div className="w-full mt-4 p-3 rounded-xl bg-red-50 border border-red-200 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500 shrink-0" />
            <span className="text-sm text-red-700">
              {scanMut.error instanceof Error ? scanMut.error.message : 'Scan failed. Check the token and try again.'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
