// All calls go to our FastAPI backend. The browser never sees an API key.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// The API key lives in localStorage on this machine only (demo convenience).
export const getKey = () => localStorage.getItem('metromind_key') || '';
export const setKey = (key) => localStorage.setItem('metromind_key', key.trim());

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}), 'X-API-Key': getKey() };
  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

const json = (data) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request('/health'),
  upload: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('/documents', { method: 'POST', body: form });
  },
  listDocuments: (params = {}) => request(`/documents?${new URLSearchParams(params)}`),
  getDocument: (id) => request(`/documents/${id}`),
  // Downloads need the key header too, so fetch the file and open it as a blob.
  openFile: async (id) => {
    const res = await fetch(`${BASE}/documents/${id}/file`, { headers: { 'X-API-Key': getKey() } });
    if (!res.ok) throw new Error(`Cannot open file (${res.status})`);
    window.open(URL.createObjectURL(await res.blob()), '_blank');
  },
  ask: (question, department, useHyde, mode) =>
    request('/ask', json({ question, department: department || null, use_hyde: useHyde, mode })),
  review: (id, department) => request(`/documents/${id}/review`, json({ department, approve: true })),
  audit: () => request('/audit'),
  stats: () => request('/stats'),
};

export const DEPARTMENTS = [
  'Engineering', 'Operations', 'Maintenance', 'Safety',
  'Finance', 'HR', 'Legal', 'Procurement',
];
