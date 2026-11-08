import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CopilotPanel from './CopilotPanel';
import { createWrapper } from '@/test/wrapper';

vi.stubEnv('VITE_USE_FIXTURES', '1');

describe('CopilotPanel', () => {
  it('renders the open button', () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    expect(screen.getByTitle('Open Copilot')).toBeInTheDocument();
  });

  it('opens panel on button click', () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByTitle('Open Copilot'));
    expect(screen.getByText('MedBalance Copilot')).toBeInTheDocument();
  });

  it('shows suggested questions in English by default', () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByTitle('Open Copilot'));
    expect(screen.getByText(/Why didn't Hesaraghatta get insulin/)).toBeInTheDocument();
    expect(screen.getByText(/Show cold-chain status/)).toBeInTheDocument();
    expect(screen.getByText(/Compare policies/)).toBeInTheDocument();
  });

  it('toggles language to Kannada', () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByTitle('Open Copilot'));
    fireEvent.click(screen.getByTitle('Toggle language'));
    expect(screen.getByText('ಕನ್ನಡ')).toBeInTheDocument();
    expect(screen.getByText(/ಈ ಯೋಜನೆಯ ಸಾರಾಂಶ ಏನು/)).toBeInTheDocument();
  });

  it('has accessible aria-label on chat input', () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByTitle('Open Copilot'));
    expect(screen.getByLabelText('Ask a question')).toBeInTheDocument();
  });

  it('shows clear button after sending a message', async () => {
    render(<CopilotPanel />, { wrapper: createWrapper() });
    fireEvent.click(screen.getByTitle('Open Copilot'));
    const input = screen.getByLabelText('Ask a question');
    fireEvent.change(input, { target: { value: 'Show cold-chain status' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByTitle('Clear conversation')).toBeInTheDocument();
  });
});
