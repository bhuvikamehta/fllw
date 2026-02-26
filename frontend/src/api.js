import axios from 'axios';

const API_URL = 'http://localhost:8000/followups'; // Fast API default

export const getPending = () => axios.get(`${API_URL}/pending`);
export const getOverdue = () => axios.get(`${API_URL}/overdue`);
export const getReport = () => axios.get(`${API_URL}/report`);
export const createFollowUp = (data) => axios.post(`${API_URL}/create`, data);
export const approveFollowUp = (id) => axios.post(`${API_URL}/${id}/approve`);
export const closeFollowUp = (id) => axios.post(`${API_URL}/${id}/close`);
export const explainFollowUp = (id) => axios.get(`${API_URL}/${id}/explain`);
