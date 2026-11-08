import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import IngestionPage from './IngestionPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getReports: () => Promise.resolve(fixtures.reports),
    getReviews: () => Promise.resolve(fixtures.reviews),
    seedDemoReports: () => Promise.resolve({ triggered: 4, reports: fixtures.reports.map(r => ({ id: r.id, facility_code: r.facility_code, items: r.items.length })) }),
    pullReports: () => Promise.resolve({ triggered: 2, facilities: ['H1', 'H2'], reports: [], errors: [] }),
    getDrugs: () => Promise.resolve(fixtures.drugs),
    resolveReview: () => Promise.resolve(fixtures.reviews[1]),
  },
}));

describe('IngestionPage', () => {
  it('renders the page title', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText('Ingestion & Review')).toBeInTheDocument();
    });
  });

  it('shows stat cards with report counts', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText('Reports Received')).toBeInTheDocument();
      expect(screen.getByText('Flagged')).toBeInTheDocument();
      expect(screen.getByText('Pending Reviews')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });
  });

  it('shows pending review banner when items need review', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText(/need pharmacist review/)).toBeInTheDocument();
    });
  });

  it('renders report cards for each facility', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText('Reports')).toBeInTheDocument();
      expect(screen.getAllByText('H1').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('H2').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('H3').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('H4').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows review queue with anomaly types', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText('Review Queue')).toBeInTheDocument();
      expect(screen.getByText('qty_spike')).toBeInTheDocument();
    });
  });

  it('shows Load demo samples and Pull hospital reports buttons', async () => {
    render(<IngestionPage />, { wrapper: createWrapper(['/ingestion']) });
    await waitFor(() => {
      expect(screen.getByText('Load demo samples')).toBeInTheDocument();
      expect(screen.getByText('Pull hospital reports')).toBeInTheDocument();
    });
  });
});
