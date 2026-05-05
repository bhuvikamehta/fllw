import React, { useState, useEffect } from 'react';
import * as api from './api';
import './App.css';

export function FollowUpCard({ item, onApprove, onClose, onExplain, onReject, onModify, onReschedule }) {
  const [draftText, setDraftText] = useState(item.current_draft || '');
  const [isEditing, setIsEditing] = useState(false);
  const [isRescheduling, setIsRescheduling] = useState(false);
  const [rescheduleTime, setRescheduleTime] = useState(
    item.next_follow_up_at ? new Date(item.next_follow_up_at).toISOString().slice(0, 16) : ''
  );

  const getStageLabel = () => {
    if (item.status === 'draft_ready' && item.current_draft?.startsWith('[REPLY_DETECTED]')) return 'Reply Detected';
    if (['draft_ready', 'awaiting_approval'].includes(item.status)) return 'Action Needed';
    if (item.status === 'sent') return 'Sent';
    return 'Waiting';
  };

  const stages = [
    { key: 'created', label: 'Created' },
    { key: 'waiting', label: getStageLabel() },
    { key: 'followed_up_1', label: 'Follow Up 1' },
    { key: 'followed_up_2', label: 'Follow Up 2' },
    { key: 'escalated', label: item.status === 'closed' ? 'Closed' : 'Escalated' }
  ];

  const getStageIndex = (status) => {
    if (status === 'created') return 0;
    if (['draft_ready', 'awaiting_approval'].includes(status)) {
      if (item.attempts_count >= 2) return 3;
      if (item.attempts_count === 1) return 2;
      return 1;
    }
    if (['waiting', 'sent'].includes(status)) return 1;
    if (status === 'followed_up_1') return 2;
    if (status === 'followed_up_2') return 3;
    if (['escalated', 'closed'].includes(status)) return 4;
    return 1;
  };
  const currentIndex = getStageIndex(item.status);

  let timeSinceLastSent = null;
  if (item.last_sent_at) {
    const diffHours = (new Date() - new Date(item.last_sent_at + (item.last_sent_at.endsWith('Z') ? '' : 'Z'))) / (1000 * 60 * 60);
    timeSinceLastSent = diffHours < 1 ? 'less than an hour ago' : `${Math.floor(diffHours)} hours ago`;
  }

  useEffect(() => {
    setDraftText(item.current_draft || '');
  }, [item.current_draft]);

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">{item.ask_summary}</h3>

        <div className="badge-group-center">
          <span className={`badge ${item.priority}`}>{item.priority}</span>
          <span className={`badge status-badge ${item.status}`}>
            {item.status.replace('_', ' ')}
          </span>
        </div>
      </div>
      <div className="card-body">
        <p><strong>Target:</strong> {item.target_contact}</p>
        <p><strong>Source:</strong> {item.source_type} ({item.source_ref})</p>
        <p><strong>Due:</strong> {new Date(item.due_at).toLocaleString()}</p>
        <p><strong>Attempts:</strong> {item.attempts_count}</p>
        {timeSinceLastSent && <p><strong>Last Sent:</strong> {timeSinceLastSent}</p>}
        {item.next_follow_up_at && <p><strong>Next Follow-up:</strong> {new Date(item.next_follow_up_at).toLocaleString()}</p>}
      </div>

      <div className="progress-container">
        {stages.map((stage, idx) => {
          let markerClass = '';
          if (idx < currentIndex) markerClass = 'completed';
          else if (idx === currentIndex) {
            markerClass = (item.status === 'escalated') ? 'escalated' : 'current';
            if (item.status === 'closed') markerClass = 'completed';
          }

          return (
            <div key={idx} className="progress-step">
              <div className={`step-marker ${markerClass}`} />
              <div className={`step-label ${markerClass}`}>{stage.label}</div>
            </div>
          );
        })}
      </div>

      {isRescheduling && (
        <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '4px' }}>
          <h4 style={{ marginBottom: '0.5rem' }}>Reschedule Follow-up</h4>
          <input
            type="datetime-local"
            className="form-control"
            value={rescheduleTime}
            onChange={e => setRescheduleTime(e.target.value)}
          />
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
            <button className="btn" onClick={() => {
              const nextTime = new Date(rescheduleTime);
              nextTime.setSeconds(0, 0);
              onReschedule(item.id, nextTime.toISOString());
              setIsRescheduling(false);
            }}>Save</button>
            <button className="btn btn-danger" onClick={() => setIsRescheduling(false)}>Cancel</button>
          </div>
        </div>
      )}

      {item.status === 'draft_ready' && item.current_draft?.startsWith('[REPLY_DETECTED]') ? (
        <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(16,185,129,0.15)', border: '1px solid var(--success)', borderRadius: '4px' }}>
          <h4 style={{ marginBottom: '0.5rem', color: 'var(--success)' }}>Reply Detected</h4>
          <p style={{ fontSize: '14px', marginBottom: '1rem' }}>A reply was found on this thread. Please acknowledge to close this follow-up.</p>
          <button className="btn" style={{ background: 'var(--success)', width: '100%' }} onClick={() => onClose(item.id)}>Acknowledge & Close</button>
        </div>
      ) : item.status === 'draft_ready' && (
        <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
          <h4 style={{ marginBottom: '0.5rem', color: 'var(--primary)' }}>Generated Draft</h4>
          {isEditing ? (
            <textarea
              value={draftText}
              onChange={e => setDraftText(e.target.value)}
              style={{ width: '100%', minHeight: '150px', background: 'var(--surface)', color: 'var(--text)', padding: '0.5rem', border: '1px solid var(--border)', fontFamily: 'inherit', textAlign: 'left' }}
            />
          ) : (
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: '13px', lineHeight: '1.5', textAlign: 'left', display: 'block', width: '100%' }}>{item.current_draft || 'No draft text saved.'}</pre>
          )}

          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            {isEditing ? (
              <button className="btn" onClick={() => { onModify(item.id, draftText); setIsEditing(false); }}>Save Edits</button>
            ) : (
              <button className="btn" style={{ background: 'rgba(255,255,255,0.1)' }} onClick={() => setIsEditing(true)}>Edit Draft</button>
            )}
            <button className="btn" style={{ background: 'var(--border)', color: 'white' }} onClick={() => onReject(item.id)}>Reject</button>
            <button className="btn" style={{ background: 'var(--primary)', flexGrow: 1 }} onClick={() => onApprove(item.id)}>Approve</button>
          </div>
        </div>
      )}

      <div className="actions" style={{ marginTop: '1rem' }}>
        {item.status !== 'closed' && item.status !== 'escalated' && (
          <button className="btn" style={{ background: 'rgba(255,255,255,0.05)' }} onClick={() => setIsRescheduling(!isRescheduling)}>Reschedule</button>
        )}
        <button className="btn" style={{ background: 'rgba(255,255,255,0.05)' }} onClick={() => onExplain(item.id)}>Explain</button>
        <button className="btn btn-danger" onClick={() => onClose(item.id)}>Close Task</button>
      </div>
    </div>
  );
}

export function CreateForm({ onCreated, workspaceId }) {
  const getLocalISOTime = () => {
    const tzoffset = (new Date()).getTimezoneOffset() * 60000;
    return (new Date(Date.now() - tzoffset)).toISOString().slice(0, 16);
  };

  const [formData, setFormData] = useState({
    workspace_id: workspaceId || '',
    requester_user_id: '',
    source_type: 'manual',
    source_ref: 'manual_entry_1',
    target_persons: '',
    ask_summary: '',
    due_date_time: getLocalISOTime(),
    urgency: 'medium',
    action_mode: 'approval_required'
  });

  // Keep workspace_id in sync if the prop loads after initial render
  useEffect(() => {
    if (workspaceId) {
      setFormData(prev => ({ ...prev, workspace_id: workspaceId }));
    }
  }, [workspaceId]);

  const [isImporting, setIsImporting] = useState(false);
  const [importStatus, setImportStatus] = useState('');
  const [threadPreview, setThreadPreview] = useState(null);

  const isEmailThread = formData.source_type === 'email';

  useEffect(() => {
    if (!isEmailThread) {
      setThreadPreview(null);
    }
  }, [isEmailThread]);

  const handleImport = async () => {
    if (!formData.source_ref) {
      alert("Please enter a Thread ID in the Source Ref field");
      return;
    }
    setIsImporting(true);
    setImportStatus('Importing...');
    try {
      const res = await api.importGmailThread(formData.source_ref);
      setThreadPreview({
        thread_id: res.data.thread_id,
        subject: res.data.subject,
        target_email: res.data.target_email,
        ask_summary: res.data.ask_summary,
      });
      setFormData(prev => ({
        ...prev,
        source_ref: res.data.thread_id || prev.source_ref,
        target_persons: res.data.target_email || prev.target_persons,
        ask_summary: res.data.ask_summary || prev.ask_summary,
      }));
      setImportStatus(`Success! ${res.data.messages_stored} messages ingested.`);
    } catch (err) {
      setThreadPreview(null);
      setImportStatus(`Import failed: ${err.response?.data?.detail || err.message}`);
    }
    setIsImporting(false);
  };
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.workspace_id) {
      alert("No workspace found. Please create or join a workspace first.");
      return;
    }
    try {
      const payload = {
        ...formData,
        target_persons: isEmailThread
          ? (formData.target_persons ? [formData.target_persons] : [])
          : formData.target_persons.split(',').map(s => s.trim()).filter(Boolean)
      };
      payload.due_date_time = new Date(payload.due_date_time).toISOString();
      await api.createFollowUp(payload);
      onCreated();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      alert("Error creating follow-up: " + detail);
    }
  };

  return (
    <form className="card" onSubmit={handleSubmit}>
      <h2 style={{ marginBottom: '1.5rem' }}>
        {isEmailThread ? 'Create Email Thread Follow-up' : 'Create Manual Follow-up'}
      </h2>
      {!workspaceId && (
        <div style={{ background: 'rgba(255, 80, 80, 0.15)', border: '1px solid var(--danger)', padding: '0.75rem 1rem', borderRadius: '6px', marginBottom: '1.5rem', fontSize: '0.9rem', color: 'var(--danger)' }}>
          You must be in a workspace to create a follow-up. Please create or join one first.
        </div>
      )}
      <div className="form-group">
        <label>Source Type</label>
        <select className="form-control" value={formData.source_type} onChange={e => setFormData({ ...formData, source_type: e.target.value })}>
          <option value="manual">Manual</option>
          <option value="email">Email Thread</option>
          {/* <option value="task">Task / Ticket</option>
          <option value="meeting">Meeting</option> */}
        </select>
      </div>
      <div className="form-group">
        <label>Source Reference (e.g. Thread ID)</label>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input required type="text" className="form-control" value={formData.source_ref} onChange={e => setFormData({ ...formData, source_ref: e.target.value })} placeholder="Thread ID or Link" />
          {isEmailThread && (
            <button type="button" className="btn" style={{ whiteSpace: 'nowrap' }} disabled={isImporting} onClick={handleImport}>
              {isImporting ? 'Importing...' : 'Import Thread Context'}
            </button>
          )}
        </div>
        {importStatus && <p style={{ fontSize: '12px', marginTop: '4px', color: importStatus.startsWith('Success') ? 'var(--primary)' : 'var(--danger)' }}>{importStatus}</p>}
      </div>
      {isEmailThread ? (
        <div style={{ marginBottom: '1.5rem', padding: '1rem', borderRadius: '10px', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Thread Details</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
            {threadPreview ? 'These values were extracted from the Gmail thread and will be used for drafting and sending.' : 'Import the Gmail thread context to auto-fill the recipient and ask summary.'}
          </p>
          <p><strong>Ask Summary:</strong> {formData.ask_summary || 'Will be inferred from the thread subject'}</p>
          <p><strong>Target Email:</strong> {formData.target_persons || 'Will be inferred from the thread participants'}</p>
        </div>
      ) : (
        <>
          <div className="form-group">
            <label>Ask Summary</label>
            <input required type="text" className="form-control" value={formData.ask_summary} onChange={e => setFormData({ ...formData, ask_summary: e.target.value })} placeholder="E.g. Get Q3 Report" />
          </div>
          <div className="form-group">
            <label>Target Email</label>
            <input required type="text" className="form-control" value={formData.target_persons} onChange={e => setFormData({ ...formData, target_persons: e.target.value })} placeholder="alice@example.com" />
          </div>
        </>
      )}
      <div className="form-group">
        <label>Due Date & Time</label>
        <input required type="datetime-local" className="form-control" value={formData.due_date_time} onChange={e => setFormData({ ...formData, due_date_time: e.target.value })} />
      </div>
      <div className="form-group">
        <label>Urgency</label>
        <select className="form-control" value={formData.urgency} onChange={e => setFormData({ ...formData, urgency: e.target.value })}>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </div>
      <div className="form-group">
        <label>Action Mode</label>
        <select className="form-control" value={formData.action_mode} onChange={e => setFormData({ ...formData, action_mode: e.target.value })}>
          <option value="approval_required">Mode A: Approval Required (Default)</option>
          <option value="draft_only">Mode B: Draft Only (Assisted)</option>
          <option value="auto_send">Mode C: Auto Send (Automated)</option>
        </select>
        {formData.action_mode === 'auto_send' && <p style={{ fontSize: '12px', color: 'var(--warning)', marginTop: '4px' }}>Note: Must pass domain/keyword validation or will fallback to Mode A.</p>}
      </div>
      <button type="submit" className="btn" style={{ width: '100%' }}>Create Follow-up</button>
    </form>
  )
}

export function ExplainModal({ data, onClose }) {
  if (!data) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <h2>Follow-up Explanation</h2>
        <div style={{ marginTop: '1rem', color: 'var(--text-muted)' }}>
          <p><strong>Pending:</strong> {data.what_is_pending}</p>
          <p><strong>Owner:</strong> {data.who_owes_it}</p>
          <p><strong>Reason:</strong> {data.why_triggered || data.reason_triggered}</p>
          <p><strong>Next steps:</strong> {data.what_happens_next || data.next_action}</p>
        </div>

        <h3 style={{ marginTop: '1.5rem' }}>Timeline</h3>
        <div className="timeline">
          {data.timeline.map((evt, idx) => (
            <div key={idx} className="timeline-item">
              <strong>{evt.event_type}</strong> - {new Date(evt.created_at).toLocaleString()}<br />
              <div style={{ marginTop: '0.5rem' }}>
                {evt.payload.reason && (
                  <p style={{ color: 'var(--text-muted)', fontStyle: 'italic', marginBottom: '0.5rem' }}>{evt.payload.reason}</p>
                )}
                {evt.payload.execution_request && (
                  <div style={{ marginTop: '0.5rem', marginBottom: '0.5rem', background: 'rgba(0,0,0,0.3)', padding: '0.5rem', borderRadius: '4px' }}>
                    <p style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--primary)', marginBottom: '0.25rem' }}>Execution Request Payload</p>
                    <pre style={{ margin: 0, fontSize: '12px', overflowX: 'auto', color: 'var(--text-muted)', textAlign: 'left' }}>
                      {JSON.stringify(evt.payload.execution_request, null, 2)}
                    </pre>
                  </div>
                )}
                {evt.payload.draft && (
                  <div style={{ background: 'rgba(255,255,255,0.05)', padding: '1rem', borderRadius: '4px', borderLeft: '3px solid var(--primary)', whiteSpace: 'pre-wrap', fontSize: '13px' }}>
                    {evt.payload.draft}
                  </div>
                )}
                {!evt.payload.reason && !evt.payload.draft && !evt.payload.execution_request && (
                  <small>{JSON.stringify(evt.payload)}</small>
                )}
              </div>
            </div>
          ))}
          {data.timeline.length === 0 && <p>No events yet.</p>}
        </div>
        <button className="btn" style={{ marginTop: '2rem', width: '100%' }} onClick={onClose}>Close</button>
      </div>
    </div>
  )
}

import Login from './Login';

const NAV_ITEMS = [
  { key: 'pending', label: 'Pending', icon: 'P' },
  { key: 'overdue', label: 'Overdue', icon: 'O' },
  { key: 'escalations', label: 'Escalations', icon: 'E' },
  { key: 'active', label: 'Active', icon: 'A' },
  { key: 'create', label: 'Create New', icon: '+' },
  { key: 'profile', label: 'Profile', icon: 'U' },
];

function decodeTokenPayload() {
  const token = localStorage.getItem('token');
  if (!token) return {};
  try {
    const payload = token.split('.')[1];
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(window.atob(normalized));
  } catch {
    return {};
  }
}

function getUserEmail() {
  const payload = decodeTokenPayload();
  return payload.email || payload.user_metadata?.email || payload.sub || 'Signed-in user';
}

function getInitial(value) {
  return (value || 'U').trim().charAt(0).toUpperCase();
}

function EmptyState({ title, message, actionLabel, onAction }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">·</div>
      <h3>{title}</h3>
      <p>{message}</p>
      {actionLabel && <button className="btn" onClick={onAction}>{actionLabel}</button>}
    </div>
  );
}

function AccountActionModal({ type, onClose, onLogout, workspaces, onJoinWorkspace }) {
  const [joinCode, setJoinCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const submitJoin = async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) return;
    setBusy(true);
    setMessage('');
    try {
      await onJoinWorkspace(joinCode.trim());
      setMessage('Organisation joined. Refreshing workspace list...');
      setJoinCode('');
    } catch (err) {
      setMessage(err.response?.data?.detail || err.message || 'Could not join organisation.');
    } finally {
      setBusy(false);
    }
  };

  const copyCode = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      setMessage('Join code copied.');
    } catch {
      setMessage('Could not copy join code.');
    }
  };

  const titleMap = {
    password: 'Change Password',
    organisation: 'Change Organisation',
    delete: 'Delete Account',
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content account-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-title-row">
          <h2>{titleMap[type]}</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">×</button>
        </div>

        {type === 'password' && (
          <div className="settings-panel">
            <p className="muted-text">Password changes need a password-reset endpoint or Supabase reset flow wired into the frontend. This keeps the UI ready without changing the working backend.</p>
            <button className="btn" onClick={() => setMessage('Password reset UI is ready; backend/auth action can be connected later.')}>Request Password Change</button>
          </div>
        )}

        {type === 'organisation' && (
          <div className="settings-panel">
            <p className="muted-text">Current organisations available to this account.</p>
            <div className="workspace-list">
              {workspaces.map(ws => (
                <div className="workspace-row" key={ws.id}>
                  <div>
                    <strong>{ws.name}</strong>
                    <span>{ws.user_role || 'member'}</span>
                  </div>
                  {ws.join_code && <button className="btn btn-subtle" onClick={() => copyCode(ws.join_code)}>Copy Code</button>}
                </div>
              ))}
              {workspaces.length === 0 && <p className="muted-text">No organisations found.</p>}
            </div>
            <form onSubmit={submitJoin} className="join-org-form">
              <input className="form-control" value={joinCode} onChange={e => setJoinCode(e.target.value)} placeholder="Enter organisation join code" />
              <button className="btn" disabled={busy}>{busy ? 'Joining...' : 'Join'}</button>
            </form>
          </div>
        )}

        {type === 'delete' && (
          <div className="settings-panel danger-zone">
            <p>Deleting an account is destructive and should be backed by a confirmed server-side auth flow. The UI action is intentionally not wired to delete anything yet.</p>
            <button className="btn btn-danger" onClick={() => setMessage('Account deletion requires a backend endpoint before it can be enabled safely.')}>Request Account Deletion</button>
          </div>
        )}

        {message && <p className="modal-message">{message}</p>}
        <div className="modal-actions">
          {type === 'delete' && <button className="btn btn-subtle" onClick={onLogout}>Logout Instead</button>}
          <button className="btn btn-subtle" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function ProfilePage({ userEmail, gmailAccount, workspaces, adminWorkspace, onConnectGmail, onLogout, onOpenAction }) {
  const activeWorkspace = workspaces[0];
  return (
    <div className="profile-page">
      <section className="profile-hero panel">
        <div className="profile-avatar large">{getInitial(userEmail)}</div>
        <div>
          <h2>{userEmail}</h2>
          <p className="muted-text">Manage your account, organisation, and connected email workspace.</p>
        </div>
      </section>

      <div className="profile-grid">
        <section className="panel">
          <div className="section-heading">
            <h3>User Information</h3>
            <span className="pill">Authenticated</span>
          </div>
          <div className="detail-list">
            <div><span>Email</span><strong>{userEmail}</strong></div>
            <div><span>Role</span><strong>{activeWorkspace?.user_role || 'Member'}</strong></div>
            <div><span>Organisation</span><strong>{activeWorkspace?.name || 'Not joined'}</strong></div>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <h3>Gmail Connection</h3>
            <span className={`pill ${gmailAccount?.send_enabled ? 'success' : ''}`}>{gmailAccount?.send_enabled ? 'Ready' : 'Needs Setup'}</span>
          </div>
          <div className="detail-list">
            <div><span>Account</span><strong>{gmailAccount?.google_email || 'Not connected'}</strong></div>
            <div><span>Send Access</span><strong>{gmailAccount?.send_enabled ? 'Enabled' : 'Not enabled'}</strong></div>
          </div>
          <button className="btn" onClick={onConnectGmail}>{gmailAccount?.connected ? 'Reconnect Gmail' : 'Connect Gmail'}</button>
        </section>

        <section className="panel">
          <div className="section-heading">
            <h3>Organisation</h3>
            <span className="pill">{workspaces.length} workspace{workspaces.length === 1 ? '' : 's'}</span>
          </div>
          <div className="detail-list">
            <div><span>Current</span><strong>{activeWorkspace?.name || 'None'}</strong></div>
            <div><span>Admin Access</span><strong>{adminWorkspace ? adminWorkspace.name : 'No admin workspace'}</strong></div>
          </div>
          <button className="btn btn-subtle" onClick={() => onOpenAction('organisation')}>Change Organisation</button>
        </section>

        <section className="panel account-actions-panel">
          <h3>Account Actions</h3>
          <button className="btn btn-subtle" onClick={() => onOpenAction('password')}>Change Password</button>
          <button className="btn btn-subtle" onClick={() => onOpenAction('organisation')}>Change Organisation</button>
          <button className="btn btn-danger" onClick={() => onOpenAction('delete')}>Delete Account</button>
          <button className="btn btn-subtle" onClick={onLogout}>Logout</button>
        </section>
      </div>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('pending');
  const [items, setItems] = useState([]);
  const [explainData, setExplainData] = useState(null);
  const [reportData, setReportData] = useState(null);
  const [navCounts, setNavCounts] = useState({});
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [myWorkspaces, setMyWorkspaces] = useState([]);
  const [adminWorkspace, setAdminWorkspace] = useState(null);
  const [workspaceMembers, setWorkspaceMembers] = useState([]);
  const [addMemberEmail, setAddMemberEmail] = useState('');
  const [addMemberRole, setAddMemberRole] = useState('user');
  const [orgDocs, setOrgDocs] = useState([]);
  const [docUploadStatus, setDocUploadStatus] = useState('');
  const [docUploading, setDocUploading] = useState(false);
  const [docType, setDocType] = useState('general');
  const [docTags, setDocTags] = useState('');
  const [viewDoc, setViewDoc] = useState(null);
  const [docContent, setDocContent] = useState('');
  const [docContentLoading, setDocContentLoading] = useState(false);
  const [gmailAccount, setGmailAccount] = useState(null);
  const [accountAction, setAccountAction] = useState(null);
  const userEmail = getUserEmail();

  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
  };

  const loadGmailStatus = async () => {
    try {
      const res = await api.getGmailStatus();
      setGmailAccount(res.data);
    } catch (err) {
      console.error('Failed to load Gmail connection status', err);
    }
  };

  const handleConnectGmail = async () => {
    try {
      const res = await api.getGmailConnectUrl(window.location.origin);
      window.location.href = res.data.url;
    } catch (err) {
      alert('Failed to start Gmail connection: ' + (err.response?.data?.detail || err.message));
    }
  };

  const loadNavigationCounts = async () => {
    try {
      const [pendingRes, overdueRes, activeRes, reportRes] = await Promise.all([
        api.getPending(),
        api.getOverdue(),
        api.getActive(),
        api.getReport(),
      ]);
      setNavCounts({
        pending: pendingRes.data.length,
        overdue: overdueRes.data.length,
        active: activeRes.data.length,
        escalations: reportRes.data.escalations?.length || 0,
      });
    } catch (err) {
      console.error('Failed to load navigation counts', err);
    }
  };

  const loadOrgDocs = async () => {
    try {
      if (!adminWorkspace) return;
      const res = await api.getOrgDocuments(adminWorkspace.id);
      setOrgDocs(res.data.documents || []);
    } catch (err) {
      console.error('Failed to load org documents', err);
    }
  };

  const handleOrgDocUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setDocUploading(true);
    setDocUploadStatus('Uploading and generating embeddings...');
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('doc_type', docType);
      form.append('tags', docTags);
      form.append('workspace_id', adminWorkspace?.id || '');
      const res = await api.uploadOrgDocument(form);
      setDocUploadStatus(`Success: "${res.data.filename}" ingested, ${res.data.chunks_stored} chunks stored.`);
      await loadOrgDocs();
    } catch (err) {
      setDocUploadStatus(`Upload failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setDocUploading(false);
      e.target.value = ''; // reset file input
    }
  };

  const handleDeleteDoc = async (filename) => {
    if (!window.confirm(`Delete "${filename}" and all its chunks from the knowledge base?`)) return;
    try {
      const res = await api.deleteOrgDocument(filename, adminWorkspace.id);
      setDocUploadStatus(`Success: "${filename}" deleted (${res.data.chunks_deleted} chunks removed).`);
      await loadOrgDocs();
    } catch (err) {
      setDocUploadStatus(`Delete failed: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDownloadDoc = async (filename) => {
    try {
      const res = await api.downloadOrgDocument(filename, adminWorkspace.id);
      const blob = new Blob([res.data], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename.replace(/\.[^.]+$/, '') + '_extracted.txt';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Download failed: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Fetch document content whenever the view modal opens
  React.useEffect(() => {
    if (!viewDoc || !adminWorkspace) { setDocContent(''); return; }
    setDocContentLoading(true);
    api.downloadOrgDocument(viewDoc.filename, adminWorkspace.id)
      .then(res => {
        const reader = new FileReader();
        reader.onload = () => setDocContent(reader.result);
        reader.readAsText(res.data);
      })
      .catch(() => setDocContent('(Could not load document content.)'))
      .finally(() => setDocContentLoading(false));
  }, [viewDoc]);

  const loadData = async () => {
    if (!isAuthenticated) return;
    try {
      if (!gmailAccount) {
        await loadGmailStatus();
      }

      // Always ensure we have workspace info
      if (myWorkspaces.length === 0) {
        const wsRes = await api.getMyWorkspaces();
        setMyWorkspaces(wsRes.data);
        const adminWs = wsRes.data.find(w => w.user_role === 'admin');
        if (adminWs) {
          setAdminWorkspace(adminWs);
        }
      }

      await loadNavigationCounts();

      if (activeTab === 'active') {
        const res = await api.getActive();
        setItems(res.data);
      } else if (activeTab === 'pending') {
        const res = await api.getPending();
        setItems(res.data);
      } else if (activeTab === 'overdue') {
        const res = await api.getOverdue();
        setItems(res.data);
      } else if (activeTab === 'escalations') {
        const res = await api.getReport();
        setReportData(res.data);
      } else if (activeTab === 'admin' && adminWorkspace) {
        const res = await api.getWorkspaceMembers(adminWorkspace.id);
        setWorkspaceMembers(res.data);
        await loadOrgDocs();
      } else {
        setItems([]);
      }
    } catch (err) {
      if (err.response?.status === 401) {
        handleLogout();
      }
      console.error(err);
    }
  };

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('gmail_connected')) {
      loadGmailStatus();
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.get('gmail_error')) {
      alert('Gmail connection failed: ' + params.get('gmail_error'));
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Auto-refresh interval (for scheduler changes)
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [activeTab, isAuthenticated]);

  const handleApprove = async (id) => {
    await api.approveFollowUp(id);
    loadData();
  };

  const handleClose = async (id) => {
    await api.closeFollowUp(id);
    loadData();
  };

  const handleReject = async (id) => {
    await api.rejectFollowUp(id);
    loadData();
  };

  const handleModify = async (id, new_text) => {
    await api.modifyFollowUp(id, new_text);
    loadData();
  };

  const handleExplain = async (id) => {
    const res = await api.explainFollowUp(id);
    setExplainData(res.data);
  };

  const handleReschedule = async (id, new_time) => {
    await api.rescheduleFollowUp(id, new_time);
    loadData();
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    if (!addMemberEmail) return;
    try {
      await api.addWorkspaceMember(adminWorkspace.id, addMemberEmail, addMemberRole);
      setAddMemberEmail('');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to add member. They may need to join via code first.");
    }
  };

  const handleRemoveMember = async (userId) => {
    if (!window.confirm("Are you sure you want to remove this member?")) return;
    try {
      await api.removeWorkspaceMember(adminWorkspace.id, userId);
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to remove member.");
    }
  };

  const handleJoinWorkspaceFromProfile = async (joinCode) => {
    await api.joinWorkspace(joinCode);
    const wsRes = await api.getMyWorkspaces();
    setMyWorkspaces(wsRes.data);
    const adminWs = wsRes.data.find(w => w.user_role === 'admin');
    setAdminWorkspace(adminWs || null);
    await loadNavigationCounts();
  };

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  const visibleNavItems = adminWorkspace
    ? [...NAV_ITEMS, { key: 'admin', label: 'Admin', icon: 'M' }]
    : NAV_ITEMS;
  const activeNav = visibleNavItems.find(item => item.key === activeTab);
  const pageSubtitle = {
    pending: 'Items waiting for action, approval, or reply detection.',
    overdue: 'Follow-ups whose due time has passed.',
    escalations: 'Final-stage items that need manual attention.',
    active: 'All non-closed follow-up work currently in motion.',
    create: 'Create a manual follow-up or connect one to an email thread.',
    admin: 'Manage workspace members and organisation knowledge.',
    profile: 'Manage your account, Gmail connection, and organisation settings.',
  }[activeTab];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">F</div>
          <div>
            <h1>Follow-Up Agent</h1>
            <p>Execution cockpit</p>
          </div>
        </div>

        <nav className="side-nav">
          {visibleNavItems.map(item => (
            <button
              key={item.key}
              className={`side-nav-btn ${activeTab === item.key ? 'active' : ''}`}
              onClick={() => setActiveTab(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
              {navCounts[item.key] !== undefined && <strong>{navCounts[item.key]}</strong>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span>Workspace</span>
          <strong>{myWorkspaces[0]?.name || 'No workspace'}</strong>
          {myWorkspaces[0]?.join_code && <small>{myWorkspaces[0].join_code}</small>}
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div>
            <h2>{activeNav?.label || 'Dashboard'}</h2>
            <p>{pageSubtitle}</p>
          </div>
          <div className="topbar-actions">
            <button className={`gmail-chip ${gmailAccount?.send_enabled ? 'connected' : ''}`} onClick={handleConnectGmail}>
              <span />
              {gmailAccount?.connected
                ? (gmailAccount.send_enabled ? gmailAccount.google_email : 'Reconnect Gmail')
                : 'Connect Gmail'}
            </button>
            <button className="profile-chip" onClick={() => setActiveTab('profile')}>
              <span className="profile-avatar">{getInitial(userEmail)}</span>
              <span>{userEmail}</span>
            </button>
          </div>
        </header>

        <main className="content-area">
          {['active', 'pending', 'overdue'].includes(activeTab) && (
            <div className="grid">
              {items.map(item => (
                <FollowUpCard
                  key={item.id}
                  item={item}
                  onApprove={handleApprove}
                  onClose={handleClose}
                  onExplain={handleExplain}
                  onReject={handleReject}
                  onModify={handleModify}
                  onReschedule={handleReschedule}
                />
              ))}
              {items.length === 0 && (
                <EmptyState
                  title={`No ${activeTab} follow-ups`}
                  message="Everything in this lane is clear right now."
                  actionLabel="Create Follow-Up"
                  onAction={() => setActiveTab('create')}
                />
              )}
            </div>
          )}

          {activeTab === 'create' && (
            <div className="form-page">
              <CreateForm onCreated={() => { setActiveTab('pending'); loadData(); }} workspaceId={myWorkspaces[0]?.id} />
            </div>
          )}

          {activeTab === 'escalations' && reportData && (
            <div>
              <div className="status-panel">
                <h3>Status Check</h3>
                <p>{reportData.blocking_you_summary}</p>
              </div>
              <h2>Escalated Items</h2>
              <div className="grid" style={{ marginTop: '1.5rem' }}>
                {reportData.escalations.map(item => (
                  <FollowUpCard
                    key={item.id}
                    item={item}
                    onApprove={handleApprove}
                    onClose={handleClose}
                    onExplain={handleExplain}
                    onReject={handleReject}
                    onModify={handleModify}
                  />
                ))}
                {reportData.escalations.length === 0 && (
                  <EmptyState
                    title="No escalations currently"
                    message="No item has reached the final escalation stage."
                    actionLabel="View Active"
                    onAction={() => setActiveTab('active')}
                  />
                )}
              </div>
            </div>
          )}

          {activeTab === 'profile' && (
            <ProfilePage
              userEmail={userEmail}
              gmailAccount={gmailAccount}
              workspaces={myWorkspaces}
              adminWorkspace={adminWorkspace}
              onConnectGmail={handleConnectGmail}
              onLogout={handleLogout}
              onOpenAction={setAccountAction}
            />
          )}

          {activeTab === 'admin' && adminWorkspace && (
            <div className="admin-page">
              <h2 style={{ marginBottom: '1.5rem' }}>Workspace Administration: {adminWorkspace.name}</h2>

              <div className="card" style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 style={{ color: 'var(--primary)' }}>Organization Join Code</h3>
                    <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem', fontSize: '0.9rem' }}>Share this code with your team members so they can join this workspace.</p>
                  </div>
                  <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.75rem 1.5rem', borderRadius: '8px', fontSize: '1.5rem', letterSpacing: '2px', fontWeight: 'bold' }}>
                    {adminWorkspace.join_code}
                  </div>
                </div>
              </div>

              {/* Users table — role can be changed inline */}
              <div className="card" style={{ marginBottom: '2rem' }}>
                <h3 style={{ marginBottom: '1.5rem' }}>Members</h3>
                <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                      <th style={{ padding: '0.5rem 0', width: '50px' }}>#</th>
                      <th style={{ padding: '0.5rem 0' }}>Email</th>
                      <th style={{ padding: '0.5rem 0' }}>Current Role</th>
                      <th style={{ padding: '0.5rem 0', textAlign: 'right' }}>Change Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workspaceMembers.map((member, index) => (
                      <tr key={member.user_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '0.75rem 0', color: 'var(--text-muted)' }}>{index + 1}</td>
                        <td style={{ padding: '0.75rem 0', fontWeight: '500' }}>{member.email || member.user_id}</td>
                        <td style={{ padding: '0.75rem 0' }}>
                          <span style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.8rem', background: member.role === 'admin' ? 'rgba(88,166,255,0.15)' : 'rgba(255,255,255,0.08)', color: member.role === 'admin' ? 'var(--primary)' : 'var(--text-muted)' }}>
                            {member.role}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 0', textAlign: 'right', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                          <select
                            className="form-control"
                            style={{ width: '110px', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                            value={addMemberRole}
                            onChange={e => setAddMemberRole(e.target.value)}
                          >
                            <option value="user">user</option>
                            <option value="admin">admin</option>
                          </select>
                          <button
                            className="btn"
                            style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}
                            onClick={async () => {
                              try {
                                await api.addWorkspaceMember(adminWorkspace.id, member.email, addMemberRole);
                                await loadData();
                              } catch (err) {
                                alert('Role change failed: ' + (err.response?.data?.detail || err.message));
                              }
                            }}
                          >Apply</button>
                          <button className="btn btn-danger" style={{ padding: '0.25rem 0.5rem', fontSize: '0.8rem' }} onClick={() => handleRemoveMember(member.user_id)}>Remove</button>
                        </td>
                      </tr>
                    ))}
                    {workspaceMembers.length === 0 && (
                      <tr><td colSpan="4" style={{ padding: '1rem 0', textAlign: 'center', color: 'var(--text-muted)' }}>No members yet.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
                <h3>Organization RAG Pipeline</h3>
                <p style={{ marginTop: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                  Upload brand guidelines, tone-of-voice documents, and product context.
                  The Follow-up Agent will use this knowledge for every draft generated in this workspace.
                </p>

                {/* Upload controls */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end', marginBottom: '1rem' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Document Type</label>
                    <select
                      className="form-control"
                      style={{ width: '140px' }}
                      value={docType}
                      onChange={e => setDocType(e.target.value)}
                    >
                      <option value="general">General</option>
                      <option value="policy">Policy</option>
                      <option value="guide">Guide</option>
                      <option value="tone">Tone of Voice</option>
                      <option value="product">Product Context</option>
                    </select>
                  </div>
                  <div style={{ flex: 1, minWidth: '160px' }}>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Tags (comma-separated)</label>
                    <input
                      type="text"
                      className="form-control"
                      placeholder="e.g. hr, onboarding"
                      value={docTags}
                      onChange={e => setDocTags(e.target.value)}
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="org-doc-upload"
                      className="btn"
                      style={{
                        display: 'inline-block',
                        cursor: docUploading ? 'not-allowed' : 'pointer',
                        opacity: docUploading ? 0.6 : 1,
                        background: 'var(--primary)',
                        padding: '0.55rem 1.1rem',
                      }}
                    >
                      {docUploading ? 'Processing...' : 'Upload Document'}
                    </label>
                    <input
                      id="org-doc-upload"
                      type="file"
                      accept=".pdf,.txt,.md"
                      style={{ display: 'none' }}
                      disabled={docUploading}
                      onChange={handleOrgDocUpload}
                    />
                  </div>
                </div>

                {docUploadStatus && (
                  <p style={{
                    fontSize: '0.85rem',
                    marginBottom: '1rem',
                    color: docUploadStatus.startsWith('Success') ? 'var(--success, #10b981)' : 'var(--danger)'
                  }}>
                    {docUploadStatus}
                  </p>
                )}

                {/* Document list */}
                <div style={{ marginTop: '0.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', overflow: 'hidden' }}>
                  {orgDocs.length === 0 ? (
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem' }}>No documents uploaded yet.</p>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-muted)' }}>
                          <th style={{ padding: '0.6rem 1rem', textAlign: 'left' }}>Filename</th>
                          <th style={{ padding: '0.6rem 1rem', textAlign: 'left' }}>Type</th>
                          <th style={{ padding: '0.6rem 1rem', textAlign: 'left' }}>Tags</th>
                          <th style={{ padding: '0.6rem 1rem', textAlign: 'right' }}>Chunks</th>
                          <th style={{ padding: '0.6rem 1rem', textAlign: 'right' }}>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orgDocs.map((doc, idx) => (
                          <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td style={{ padding: '0.6rem 1rem', fontWeight: 500 }}>{doc.filename}</td>
                            <td style={{ padding: '0.6rem 1rem', color: 'var(--text-muted)' }}>{doc.doc_type}</td>
                            <td style={{ padding: '0.6rem 1rem', color: 'var(--text-muted)' }}>
                              {doc.tags?.length > 0 ? doc.tags.join(', ') : '-'}
                            </td>
                            <td style={{ padding: '0.6rem 1rem', textAlign: 'right', color: 'var(--primary)' }}>{doc.chunks}</td>
                            <td style={{ padding: '0.6rem 1rem', textAlign: 'right', display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
                              <button
                                className="btn"
                                style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem', background: 'rgba(255,255,255,0.07)' }}
                                onClick={() => setViewDoc(doc)}
                              >View</button>
                              <button
                                className="btn"
                                style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem', background: 'rgba(16,185,129,0.15)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.25)' }}
                                onClick={() => handleDownloadDoc(doc.filename)}
                              >Download</button>
                              <button
                                className="btn btn-danger"
                                style={{ padding: '0.2rem 0.6rem', fontSize: '0.8rem' }}
                                onClick={() => handleDeleteDoc(doc.filename)}
                              >Delete</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {explainData && (
        <ExplainModal data={explainData} onClose={() => setExplainData(null)} />
      )}

      {accountAction && (
        <AccountActionModal
          type={accountAction}
          onClose={() => setAccountAction(null)}
          onLogout={handleLogout}
          workspaces={myWorkspaces}
          onJoinWorkspace={handleJoinWorkspaceFromProfile}
        />
      )}

      {viewDoc && (
        <div className="modal-overlay" onClick={() => setViewDoc(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '640px', display: 'flex', flexDirection: 'column', maxHeight: '85vh' }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
              <h3 style={{ fontSize: '1.1rem', margin: 0 }}>{viewDoc.filename}</h3>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                <span style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.78rem', background: 'rgba(99,102,241,0.2)', color: 'var(--primary)' }}>{viewDoc.doc_type}</span>
                {viewDoc.tags?.map(t => (
                  <span key={t} style={{ padding: '0.2rem 0.6rem', borderRadius: '4px', fontSize: '0.78rem', background: 'rgba(255,255,255,0.08)', color: 'var(--text-muted)' }}>{t}</span>
                ))}
              </div>
            </div>

            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
              {viewDoc.chunks} chunk{viewDoc.chunks !== 1 ? 's' : ''} - extracted text stored for semantic retrieval
            </p>

            {/* Content area */}
            <div style={{
              flex: 1, overflowY: 'auto', background: 'rgba(15,23,42,0.7)',
              border: '1px solid var(--border)', borderRadius: '10px',
              padding: '1rem', marginBottom: '1.25rem', minHeight: '180px',
            }}>
              {docContentLoading ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading...</p>
              ) : (
                <pre style={{
                  margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  fontSize: '0.82rem', color: 'var(--text-main)', lineHeight: 1.65,
                  fontFamily: "'Courier New', Courier, monospace",
                }}>{docContent}</pre>
              )}
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              <button className="btn btn-danger" onClick={() => { handleDeleteDoc(viewDoc.filename); setViewDoc(null); }}>Delete</button>
              <button className="btn" style={{ background: 'rgba(16,185,129,0.15)', color: 'var(--success)', border: '1px solid rgba(16,185,129,0.3)' }} onClick={() => handleDownloadDoc(viewDoc.filename)}>Download</button>
              <button className="btn" style={{ background: 'rgba(255,255,255,0.07)' }} onClick={() => setViewDoc(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
