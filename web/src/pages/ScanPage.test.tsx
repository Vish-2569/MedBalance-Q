import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ScanPage from './ScanPage';
import { createWrapper } from '@/test/wrapper';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: vi.fn(() => ({ token: 'ORD-004' })) };
});

const resolveQrTokenMock = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    id: 'ORD-004', dta_number: 'DTA/BLR-U/2026/000004', plan_id: 'plan-demo-001',
    src_facility_id: 'W0', dst_facility_id: 'H3',
    drug_code: 'ORS', drug_name: 'ORS Sachet',
    batch_no: 'B-OR-2026-001', qty: 125, usable: 125, score: 0.80,
    status: 'approved', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30',
  })
);

vi.mock('@/lib/api', () => ({
  api: {
    resolveQrToken: resolveQrTokenMock,
    custodyScan: () => Promise.resolve({ order_id: 'ORD-004', event: 'dispatch', status: 'dispatched', qty: 125 }),
  },
}));

describe('ScanPage', () => {
  it('shows the order DTA number when token matches an order', async () => {
    render(<ScanPage />, { wrapper: createWrapper(['/scan/ORD-004']) });
    await waitFor(() => {
      expect(screen.getByText('DTA/BLR-U/2026/000004')).toBeInTheDocument();
    });
  });

  it('shows drug name', async () => {
    render(<ScanPage />, { wrapper: createWrapper(['/scan/ORD-004']) });
    await waitFor(() => {
      expect(screen.getByText('ORS Sachet')).toBeInTheDocument();
    });
  });

  it('shows Dispatch button for an approved order', async () => {
    render(<ScanPage />, { wrapper: createWrapper(['/scan/ORD-004']) });
    await waitFor(() => {
      expect(screen.getByText('Dispatch')).toBeInTheDocument();
    });
  });

  it('shows no-token message when token param is absent', async () => {
    const { useParams } = await import('react-router-dom');
    vi.mocked(useParams).mockReturnValueOnce({});
    render(<ScanPage />, { wrapper: createWrapper(['/scan']) });
    expect(screen.getByText('No scan token provided')).toBeInTheDocument();
    vi.mocked(useParams).mockReturnValue({ token: 'ORD-004' });
  });

  it('shows Order not found when token lookup fails', async () => {
    resolveQrTokenMock.mockRejectedValueOnce(new Error('Order not found'));
    render(<ScanPage />, { wrapper: createWrapper(['/scan/ORD-004']) });
    await waitFor(() => {
      expect(screen.getByText(/not found|unavailable/i)).toBeInTheDocument();
    });
  });
});
