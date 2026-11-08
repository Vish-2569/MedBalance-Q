import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ResultsPage from './ResultsPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getPlanDemo: () => Promise.resolve(fixtures.planDemo),
    getPositions: () => Promise.resolve(fixtures.positions),
  },
}));

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

describe('ResultsPage', () => {
  it('renders the page title', async () => {
    render(<ResultsPage />, { wrapper: createWrapper(['/results']) });
    await waitFor(() => {
      expect(screen.getByText('Results Dashboard')).toBeInTheDocument();
    });
  });

  it('shows metric cards with plan data', async () => {
    render(<ResultsPage />, { wrapper: createWrapper(['/results']) });
    await waitFor(() => {
      expect(screen.getByText('Transfer Orders')).toBeInTheDocument();
      expect(screen.getByText('Units Proposed')).toBeInTheDocument();
      const shortageElements = screen.getAllByText('Shortage Reduction');
      expect(shortageElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('renders ablation section', async () => {
    render(<ResultsPage />, { wrapper: createWrapper(['/results']) });
    await waitFor(() => {
      const ablationElements = screen.getAllByText(/Policy Ablation/);
      expect(ablationElements.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows [Illustrative] badge on ablation section', async () => {
    render(<ResultsPage />, { wrapper: createWrapper(['/results']) });
    await waitFor(() => {
      expect(screen.getByText('[Illustrative]')).toBeInTheDocument();
    });
  });

  it('shows CI bounds for QUBO', async () => {
    render(<ResultsPage />, { wrapper: createWrapper(['/results']) });
    await waitFor(() => {
      // formatPct(0.513) = "51%", formatPct(0.528) = "53%"
      expect(screen.getByText(/QUBO 95% CI: \[51%, 53%\]/)).toBeInTheDocument();
    });
  });
});
