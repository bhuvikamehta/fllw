import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const API_URL = `${BASE_URL}/followups`; // Fast API default
const AUTH_URL = `${BASE_URL}/auth`;

axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  return axios.post(`${AUTH_URL}/login`, formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  });
};

export const register = (email, password) => axios.post(`${AUTH_URL}/register`, { email, password });
export const getGoogleAuthUrl = () => axios.get(`${AUTH_URL}/login/google`);
export const getGmailStatus = () => axios.get(`${AUTH_URL}/gmail/status`);
export const getGmailConnectUrl = (frontend_url) => axios.get(`${AUTH_URL}/gmail/connect`, {
  params: frontend_url ? { frontend_url } : {},
});

const WORKSPACE_URL = `${BASE_URL}/workspaces`;
export const createWorkspace = (name) => axios.post(`${WORKSPACE_URL}`, { name });
export const joinWorkspace = (join_code) => axios.post(`${WORKSPACE_URL}/join`, { join_code });
export const getMyWorkspaces = () => axios.get(`${WORKSPACE_URL}/me`);
export const getWorkspaceMembers = (id) => axios.get(`${WORKSPACE_URL}/${id}/members`);
export const addWorkspaceMember = (id, email, role) => axios.post(`${WORKSPACE_URL}/${id}/members`, { email, role });
export const removeWorkspaceMember = (id, user_id) => axios.delete(`${WORKSPACE_URL}/${id}/members/${user_id}`);


export const getPending = () => axios.get(`${API_URL}/pending`);
export const getOverdue = () => axios.get(`${API_URL}/overdue`);
export const getReport = () => axios.get(`${API_URL}/report`);
export const createFollowUp = (data) => axios.post(`${API_URL}/create`, data);
export const approveFollowUp = (id) => axios.post(`${API_URL}/${id}/approve`);
export const rejectFollowUp = (id) => axios.post(`${API_URL}/${id}/reject`);
export const modifyFollowUp = (id, new_text) => axios.post(`${API_URL}/${id}/modify`, { new_text });
export const closeFollowUp = (id) => axios.post(`${API_URL}/${id}/close`);
export const explainFollowUp = (id) => axios.get(`${API_URL}/${id}/explain`);
export const getActive = () => axios.get(`${API_URL}/active`);
export const rescheduleFollowUp = (id, new_time) => axios.post(`${API_URL}/${id}/reschedule`, { new_time });
export const importGmailThread = (threadId) => axios.post(`${BASE_URL}/ingest/gmail_thread/${threadId}`);

export const uploadOrgDocument = (formData) =>
  axios.post(`${BASE_URL}/ingest/org_document`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const getOrgDocuments = (workspaceId) => axios.get(`${BASE_URL}/ingest/org_documents?workspace_id=${workspaceId}`);

export const deleteOrgDocument = (filename, workspaceId) =>
  axios.delete(`${BASE_URL}/ingest/org_document?filename=${encodeURIComponent(filename)}&workspace_id=${workspaceId}`);

export const downloadOrgDocument = (filename, workspaceId) => {
  // Streaming download — open directly so the browser handles the file save dialog
  const token = localStorage.getItem('token');
  const url = `${BASE_URL}/ingest/org_document/download?filename=${encodeURIComponent(filename)}&workspace_id=${workspaceId}`;
  // Fetch as blob so we can attach the auth header (endpoint is auth-guarded)
  return axios.get(url, {
    headers: { Authorization: `Bearer ${token}` },
    responseType: 'blob',
  });
};
