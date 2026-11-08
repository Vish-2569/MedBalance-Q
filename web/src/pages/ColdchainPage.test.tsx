import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ColdchainPage from './ColdchainPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getColdchain: () => Promise.resolve(fixtures.coldchain),
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

describe('ColdchainPage', () => {
  it('renders the page title', async () => {
    render(<ColdchainPage />, { wrapper: createWrapper(['/coldchain']) });
    await waitFor(() => {
      expect(screen.getByText('Cold Chain Monitoring')).toBeInTheDocument();
    });
  });

  it('shows excursion banner when sensor is in excursion', async () => {
    render(<ColdchainPage />, { wrapper: createWrapper(['/coldchain']) });
    await waitFor(() => {
      expect(screen.getByText('Cold Chain Excursion Detected')).toBeInTheDocument();
    });
  });

  it('shows stat cards', async () => {
    render(<ColdchainPage />, { wrapper: createWrapper(['/coldchain']) });
    await waitFor(() => {
      expect(screen.getByText('Devices')).toBeInTheDocument();
      expect(screen.getAllByText('OK').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Excursions')).toBeInTheDocument();
    });
  });

  it('renders device cards with sensor IDs', async () => {
    render(<ColdchainPage />, { wrapper: createWrapper(['/coldchain']) });
    await waitFor(() => {
      expect(screen.getByText('sensor-01')).toBeInTheDocument();
      expect(screen.getByText('sensor-02')).toBeInTheDocument();
      expect(screen.getByText('sensor-03')).toBeInTheDocument();
    });
  });

  it('shows temperature readings', async () => {
    render(<ColdchainPage />, { wrapper: createWrapper(['/coldchain']) });
    await waitFor(() => {
      expect(screen.getByText('4.2°C')).toBeInTheDocument();
      expect(screen.getByText('9.8°C')).toBeInTheDocument();
    });
  });
});
