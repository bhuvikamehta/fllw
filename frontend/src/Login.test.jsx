import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import Login from './Login';
import * as api from './api';

vi.mock('./api', () => ({
  login: vi.fn(),
  register: vi.fn(),
  createWorkspace: vi.fn(),
  joinWorkspace: vi.fn(),
  getGoogleAuthUrl: vi.fn(),
}));

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('signs in, stores the token, and notifies the app', async () => {
    const user = userEvent.setup();
    const onLoginSuccess = vi.fn();
    api.login.mockResolvedValue({ data: { access_token: 'test-token' } });

    render(<Login onLoginSuccess={onLoginSuccess} />);

    await user.type(screen.getByPlaceholderText('Email address'), 'tester@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'secret123');
    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    await waitFor(() => expect(api.login).toHaveBeenCalledWith('tester@example.com', 'secret123'));
    expect(localStorage.getItem('token')).toBe('test-token');
    expect(onLoginSuccess).toHaveBeenCalledTimes(1);
  });

  it('registers a new organization account and creates the workspace after login', async () => {
    const user = userEvent.setup();
    const onLoginSuccess = vi.fn();
    api.register.mockResolvedValue({});
    api.login.mockResolvedValue({ data: { access_token: 'new-token' } });
    api.createWorkspace.mockResolvedValue({ data: { join_code: 'ORG12345' } });

    render(<Login onLoginSuccess={onLoginSuccess} />);

    await user.click(screen.getByRole('button', { name: 'Register' }));
    await user.click(screen.getByRole('button', { name: 'Create Organization' }));
    await user.type(screen.getByPlaceholderText('Organization Name'), 'Acme Ops');
    await user.type(screen.getByPlaceholderText('Email address'), 'founder@example.com');
    await user.type(screen.getByPlaceholderText('Password'), 'secret123');
    await user.click(screen.getByRole('button', { name: 'Create Account' }));

    await waitFor(() => expect(api.register).toHaveBeenCalledWith('founder@example.com', 'secret123'));
    expect(api.login).toHaveBeenCalledWith('founder@example.com', 'secret123');
    expect(api.createWorkspace).toHaveBeenCalledWith('Acme Ops');
    expect(localStorage.getItem('pending_org_name')).toBeNull();
    expect(onLoginSuccess).toHaveBeenCalledTimes(1);
  });

  it('toggles password visibility', async () => {
    const user = userEvent.setup();
    render(<Login onLoginSuccess={vi.fn()} />);

    const passwordInput = screen.getByPlaceholderText('Password');
    expect(passwordInput).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(passwordInput).toHaveAttribute('type', 'text');

    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(passwordInput).toHaveAttribute('type', 'password');
  });
});
