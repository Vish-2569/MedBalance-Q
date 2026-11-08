import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AIHealthPage from './AIHealthPage';
import { createWrapper } from '@/test/wrapper';
import * as fixtures from '@/fixtures';

vi.stubEnv('VITE_USE_FIXTURES', '1');

vi.mock('@/lib/api', () => ({
  api: {
    getAIHealth: () => Promise.resolve({ ...fixtures.aiHealth, total_calls: 0 }),
  },
}));

describe('AIHealthPage', () => {
  it('renders the page title', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      expect(screen.getByText('AI Health')).toBeInTheDocument();
    });
  });

  it('shows demo banner when total_calls is 0', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      expect(screen.getByText(/illustrative fixture values/)).toBeInTheDocument();
    });
  });

  it('shows (demo) suffix on stat cards', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      const demoLabels = screen.getAllByText('(demo)');
      expect(demoLabels.length).toBeGreaterThan(0);
    });
  });

  it('shows [Illustrative] badge on eval scores', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      expect(screen.getByText('[Illustrative]')).toBeInTheDocument();
    });
  });

  it('shows eval score bars', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      const items = screen.getAllByText('extract_stock');
      expect(items.length).toBeGreaterThan(0);
      const narrate = screen.getAllByText('narrate_order');
      expect(narrate.length).toBeGreaterThan(0);
    });
  });

  it('shows provider info', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      expect(screen.getByText('Gemini')).toBeInTheDocument();
      expect(screen.getByText('gemini-2.0-flash')).toBeInTheDocument();
    });
  });

  it('shows golden rule reminder', async () => {
    render(<AIHealthPage />, { wrapper: createWrapper(['/ai-health']) });
    await waitFor(() => {
      const goldenRuleElements = screen.getAllByText(/LLMs read and explain/);
      expect(goldenRuleElements.length).toBeGreaterThanOrEqual(1);
    });
  });
});
