import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { CreateForm, ExplainModal, FollowUpCard } from './App';
import * as api from './api';

vi.mock('./api', () => ({
  createFollowUp: vi.fn(),
  importGmailThread: vi.fn(),
}));

function makeItem(overrides = {}) {
  return {
    id: 'fu_1',
    ask_summary: 'Send the project update',
    target_contact: 'owner@example.com',
    source_type: 'manual',
    source_ref: 'manual_1',
    due_at: '2026-05-05T10:30:00Z',
    status: 'draft_ready',
    priority: 'medium',
    attempts_count: 0,
    channel: 'email',
    mode: 'approval_required',
    current_draft: 'Hi,\n\nPlease send the project update.\n\nRegards,',
    created_at: '2026-05-04T10:30:00Z',
    updated_at: '2026-05-04T10:30:00Z',
    ...overrides,
  };
}

describe('FollowUpCard', () => {
  it('lets a user edit and save a generated draft', async () => {
    const user = userEvent.setup();
    const onModify = vi.fn();

    render(
      <FollowUpCard
        item={makeItem()}
        onApprove={vi.fn()}
        onClose={vi.fn()}
        onExplain={vi.fn()}
        onReject={vi.fn()}
        onModify={onModify}
        onReschedule={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Edit Draft' }));
    const editor = screen.getByRole('textbox');
    await user.clear(editor);
    await user.type(editor, 'Updated draft text');
    await user.click(screen.getByRole('button', { name: 'Save Edits' }));

    expect(onModify).toHaveBeenCalledWith('fu_1', 'Updated draft text');
  });

  it('shows reply-detected acknowledgement and closes on acknowledgement', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <FollowUpCard
        item={makeItem({ current_draft: '[REPLY_DETECTED] Normal reply found.' })}
        onApprove={vi.fn()}
        onClose={onClose}
        onExplain={vi.fn()}
        onReject={vi.fn()}
        onModify={vi.fn()}
        onReschedule={vi.fn()}
      />,
    );

    expect(screen.getAllByText('Reply Detected').length).toBeGreaterThan(0);
    await user.click(screen.getByRole('button', { name: 'Acknowledge & Close' }));

    expect(onClose).toHaveBeenCalledWith('fu_1');
  });

  it('calls reschedule with the selected datetime', async () => {
    const user = userEvent.setup();
    const onReschedule = vi.fn();

    render(
      <FollowUpCard
        item={makeItem({ status: 'waiting', current_draft: null })}
        onApprove={vi.fn()}
        onClose={vi.fn()}
        onExplain={vi.fn()}
        onReject={vi.fn()}
        onModify={vi.fn()}
        onReschedule={onReschedule}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Reschedule' }));
    await user.type(screen.getByDisplayValue(''), '2026-05-05T10:30');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    expect(onReschedule).toHaveBeenCalledWith('fu_1', expect.stringContaining('2026-05-05T'));
  });
});

describe('CreateForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits a manual follow-up payload and notifies the parent', async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    api.createFollowUp.mockResolvedValue({ data: {} });

    render(<CreateForm workspaceId="ws_1" onCreated={onCreated} />);

    await user.clear(screen.getByPlaceholderText('E.g. Get Q3 Report'));
    await user.type(screen.getByPlaceholderText('E.g. Get Q3 Report'), 'Send the Q3 report');
    await user.type(screen.getByPlaceholderText('alice@example.com'), 'alice@example.com');
    await user.click(screen.getByRole('button', { name: 'Create Follow-up' }));

    await waitFor(() => expect(api.createFollowUp).toHaveBeenCalledTimes(1));
    const payload = api.createFollowUp.mock.calls[0][0];
    expect(payload.workspace_id).toBe('ws_1');
    expect(payload.source_type).toBe('manual');
    expect(payload.target_persons).toEqual(['alice@example.com']);
    expect(payload.ask_summary).toBe('Send the Q3 report');
    expect(payload.due_date_time).toMatch(/T/);
    expect(onCreated).toHaveBeenCalledTimes(1);
  });

  it('imports Gmail thread context and auto-fills email fields', async () => {
    const user = userEvent.setup();
    api.importGmailThread.mockResolvedValue({
      data: {
        thread_id: 'abc123def456789',
        subject: 'Project update',
        target_email: 'owner@example.com',
        ask_summary: 'Send project update',
        messages_stored: 2,
      },
    });

    render(<CreateForm workspaceId="ws_1" onCreated={vi.fn()} />);

    await user.selectOptions(screen.getAllByRole('combobox')[0], 'email');
    const sourceInput = screen.getByPlaceholderText('Thread ID or Link');
    await user.clear(sourceInput);
    await user.type(sourceInput, 'Project update');
    await user.click(screen.getByRole('button', { name: 'Import Thread Context' }));

    await waitFor(() => expect(api.importGmailThread).toHaveBeenCalledWith('Project update'));
    expect(screen.getByText(/Success! 2 messages ingested./)).toBeInTheDocument();
    expect(screen.getByText(/Send project update/)).toBeInTheDocument();
    expect(screen.getByText(/owner@example.com/)).toBeInTheDocument();
  });
});

describe('ExplainModal', () => {
  it('renders backend explanation fields and timeline events', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <ExplainModal
        onClose={onClose}
        data={{
          what_is_pending: 'Send report',
          who_owes_it: 'owner@example.com',
          reason_triggered: 'Draft was generated because due time was reached.',
          next_action: 'Waiting for user approval.',
          timeline: [
            {
              event_type: 'transition_draft_ready',
              created_at: '2026-05-05T10:30:00Z',
              payload: { reason: 'due_time_reached', draft: 'Hi there' },
            },
          ],
        }}
      />,
    );

    expect(screen.getByText(/Send report/)).toBeInTheDocument();
    expect(screen.getByText(/Draft was generated/)).toBeInTheDocument();
    expect(screen.getByText(/Waiting for user approval/)).toBeInTheDocument();
    expect(screen.getByText('transition_draft_ready')).toBeInTheDocument();
    expect(screen.getByText('Hi there')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
