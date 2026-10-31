// All calls go to our FastAPI backend. The browser never sees an API key.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
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
  fileUrl: (id) => `${BASE}/documents/${id}/file`,
  ask: (question, department) => request('/ask', json({ question, department: department || null })),
  review: (id, department) => request(`/documents/${id}/review`, json({ department, approve: true })),
  audit: () => request('/audit'),
  stats: () => request('/stats'),
};

export const DEPARTMENTS = [
  'Engineering', 'Operations', 'Maintenance', 'Safety',
  'Finance', 'HR', 'Legal', 'Procurement',
];
