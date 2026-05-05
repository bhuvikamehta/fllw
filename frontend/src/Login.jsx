import React, { useState, useEffect } from 'react';
import * as api from './api';

function EyeIcon({ visible }) {
  return visible ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function Login({ onLoginSuccess }) {
  const [mode, setMode] = useState('login'); // 'login', 'register_user', 'register_org'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [joinCode, setJoinCode] = useState('');
  const [orgName, setOrgName] = useState('');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handlePostLoginTasks = async () => {
    const pendingJoinCode = localStorage.getItem('pending_join_code');
    const pendingOrgName = localStorage.getItem('pending_org_name');

    try {
      if (pendingJoinCode) {
        await api.joinWorkspace(pendingJoinCode);
        localStorage.removeItem('pending_join_code');
        setSuccessMsg('Successfully joined the organization!');
      } else if (pendingOrgName) {
        const res = await api.createWorkspace(pendingOrgName);
        localStorage.removeItem('pending_org_name');
        setSuccessMsg(`Organization created! Your Join Code is: ${res.data.join_code}`);
      }
    } catch (err) {
      console.error("Post-login task error", err);
    }
  };

  useEffect(() => {
    const hash = window.location.hash;
    if (hash && hash.includes('access_token')) {
      const params = new URLSearchParams(hash.substring(1));
      const token = params.get('access_token');
      if (token) {
        localStorage.setItem('token', token);
        window.location.hash = '';
        handlePostLoginTasks().finally(() => {
          onLoginSuccess();
        });
      }
    }
  }, [onLoginSuccess]);

  const handleGoogleLogin = async () => {
    try {
      if (mode === 'register_user' && joinCode) {
        localStorage.setItem('pending_join_code', joinCode);
      } else if (mode === 'register_org' && orgName) {
        localStorage.setItem('pending_org_name', orgName);
      }
      const res = await api.getGoogleAuthUrl();
      window.location.href = res.data.url;
    } catch (err) {
      setError('Failed to initiate Google login');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setLoading(true);

    try {
      if (mode === 'register_user' || mode === 'register_org') {
        if (mode === 'register_user' && joinCode) {
          localStorage.setItem('pending_join_code', joinCode);
        } else if (mode === 'register_org' && orgName) {
          localStorage.setItem('pending_org_name', orgName);
        }

        await api.register(email, password);
        const res = await api.login(email, password);
        localStorage.setItem('token', res.data.access_token);
        await handlePostLoginTasks();
        onLoginSuccess();
      } else {
        const res = await api.login(email, password);
        localStorage.setItem('token', res.data.access_token);
        await handlePostLoginTasks();
        onLoginSuccess();
      }
    } catch (err) {
      let errorMsg = err.response?.data?.detail || err.message || 'An error occurred';
      if (typeof errorMsg === 'string') {
        if (errorMsg.toLowerCase().includes('email not confirmed')) {
          errorMsg = 'Please check your email inbox and click the confirmation link to verify your account before logging in.';
        } else if (errorMsg.toLowerCase().includes('rate limit')) {
          errorMsg = 'You have tried to register too many times recently. Please wait a while or disable email confirmations in your Supabase dashboard.';
        }
      }
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form className="login-card" onSubmit={handleSubmit}>
        <h2 className="login-title">
          {mode === 'login' ? 'Welcome Back' : 'Create Account'}
        </h2>
        <p className="login-subtitle">
          {mode === 'login' ? 'Access your intelligent agent' : 'Join the autonomous execution platform'}
        </p>

        {mode !== 'login' && (
          <div style={{ display: 'flex', gap: '10px', marginBottom: '1.5rem' }}>
            <button
              type="button"
              onClick={() => setMode('register_user')}
              style={{ flex: 1, padding: '8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: mode === 'register_user' ? 'rgba(255,255,255,0.1)' : 'transparent', color: 'white', cursor: 'pointer' }}
            >
              Join Organization
            </button>
            <button
              type="button"
              onClick={() => setMode('register_org')}
              style={{ flex: 1, padding: '8px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.2)', background: mode === 'register_org' ? 'rgba(255,255,255,0.1)' : 'transparent', color: 'white', cursor: 'pointer' }}
            >
              Create Organization
            </button>
          </div>
        )}

        <div style={{ marginBottom: '1.5rem' }}>
          <button type="button" className="login-btn-google" onClick={handleGoogleLogin}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z" /></svg>
            Continue with Google
          </button>
          <div className="login-divider">Or</div>
        </div>

        {successMsg && (
          <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success)', padding: '0.875rem', borderRadius: '12px', marginBottom: '1.25rem', fontSize: '0.9rem', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
            {successMsg}
          </div>
        )}

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--danger)', padding: '0.875rem', borderRadius: '12px', marginBottom: '1.25rem', fontSize: '0.9rem', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
            {error}
          </div>
        )}

        {mode === 'register_user' && (
          <div className="login-input-group">
            <input
              type="text"
              className="login-input"
              value={joinCode}
              onChange={e => setJoinCode(e.target.value)}
              required
              placeholder="Organization Join Code (e.g. MOCK-123)"
            />
          </div>
        )}

        {mode === 'register_org' && (
          <div className="login-input-group">
            <input
              type="text"
              className="login-input"
              value={orgName}
              onChange={e => setOrgName(e.target.value)}
              required
              placeholder="Organization Name"
            />
          </div>
        )}

        <div className="login-input-group">
          <input
            type="email"
            className="login-input"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            placeholder="Email address"
          />
        </div>
        <div className="login-input-group">
          <div className="password-wrapper">
            <input
              type={showPassword ? 'text' : 'password'}
              className="login-input password-input"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="Password"
              minLength={mode !== 'login' ? 6 : undefined}
            />

            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(v => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              <EyeIcon visible={showPassword} />
            </button>
          </div>

          {mode !== 'login' && (
            <small className="password-hint">
              Password must be at least 6 characters.
            </small>
          )}
        </div>

        <button type="submit" className="login-btn-primary" disabled={loading}>
          {loading ? 'Processing...' : (mode !== 'login' ? 'Create Account' : 'Sign In')}
        </button>

        <p style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
          {mode !== 'login' ? 'Already have an account?' : "Don't have an account?"}
          <button
            type="button"
            className="login-toggle-link"
            style={{ marginLeft: '0.5rem' }}
            onClick={() => setMode(mode === 'login' ? 'register_user' : 'login')}
          >
            {mode !== 'login' ? 'Sign In' : 'Register'}
          </button>
        </p>
      </form>
    </div>
  );
}

export default Login;
