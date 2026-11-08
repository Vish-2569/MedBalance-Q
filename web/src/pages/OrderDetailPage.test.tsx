import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import OrderDetailPage from './OrderDetailPage';
import { createWrapper } from '@/test/wrapper';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: vi.fn(() => ({ id: 'ORD-001' })) };
});

const rejectOrderMock = vi.hoisted(() => vi.fn().mockResolvedValue({}));

vi.mock('@/lib/api', () => ({
  api: {
    getOrder: () => Promise.resolve({
      id: 'ORD-001', dta_number: 'DTA/BLR-U/2026/000001', plan_id: 'plan-demo-001',
      src_facility_id: 'W0', dst_facility_id: 'H2',
      drug_code: 'PARA500', drug_name: 'Paracetamol 500mg',
      batch_no: 'B-PA-2026-001', qty: 180, usable: 180, score: 0.92,
      status: 'proposed', temperature_req: 'ambient', created_at: '2026-11-01T10:30:00+05:30',
    }),
    getProvenance: () => Promise.resolve({ nodes: [], edges: [] }),
    getCustody: () => Promise.resolve([]),
    getRegret: () => Promise.resolve([]),
    getFacilities: () => Promise.resolve([]),
    approveOrder: () => Promise.resolve({}),
    rejectOrder: rejectOrderMock,
  },
}));

describe('OrderDetailPage', () => {
  beforeEach(() => {
    rejectOrderMock.mockClear();
    vi.spyOn(window, 'prompt').mockReturnValue(null);
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  it('renders the DTA number', async () => {
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => {
      expect(screen.getByText('DTA/BLR-U/2026/000001')).toBeInTheDocument();
    });
  });

  it('shows drug name and quantity', async () => {
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => {
      expect(screen.getByText('Paracetamol 500mg')).toBeInTheDocument();
    });
  });

  it('shows Approve and Reject buttons for a proposed order', async () => {
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
      expect(screen.getByText('Reject')).toBeInTheDocument();
    });
  });

  it('reject: does nothing when prompt is cancelled', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue(null);
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => screen.getByText('Reject'));
    fireEvent.click(screen.getByText('Reject'));
    expect(rejectOrderMock).not.toHaveBeenCalled();
  });

  it('reject: does nothing when reason is blank', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('   ');
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => screen.getByText('Reject'));
    fireEvent.click(screen.getByText('Reject'));
    expect(rejectOrderMock).not.toHaveBeenCalled();
  });

  it('reject: shows alert and does not call API when reason exceeds 500 chars', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('x'.repeat(501));
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => screen.getByText('Reject'));
    fireEvent.click(screen.getByText('Reject'));
    expect(alertSpy).toHaveBeenCalledWith('Reason must be 500 characters or fewer.');
    expect(rejectOrderMock).not.toHaveBeenCalled();
  });

  it('reject: exactly 500 chars is accepted and calls API', async () => {
    const reason500 = 'a'.repeat(500);
    vi.spyOn(window, 'prompt').mockReturnValue(reason500);
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => screen.getByText('Reject'));
    fireEvent.click(screen.getByText('Reject'));
    await waitFor(() => expect(rejectOrderMock).toHaveBeenCalledWith('ORD-001', reason500));
  });

  it('reject: trims whitespace and calls API with trimmed reason', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('  Expired batch  ');
    render(<OrderDetailPage />, { wrapper: createWrapper(['/orders/ORD-001']) });
    await waitFor(() => screen.getByText('Reject'));
    fireEvent.click(screen.getByText('Reject'));
    await waitFor(() => expect(rejectOrderMock).toHaveBeenCalledWith('ORD-001', 'Expired batch'));
  });
});
