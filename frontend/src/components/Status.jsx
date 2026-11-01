// One place that decides how a status or a department looks, so every tab agrees.
const STATUS_COLOR = { ANALYZED: 'green', APPROVED: 'green', NEEDS_REVIEW: 'amber', REJECTED: 'red', DUPLICATE: 'grey' };
const STATUS_LABEL = { NEEDS_REVIEW: 'Needs review' };

export function StatusBadge({ status }) {
  const label = STATUS_LABEL[status] || (status ? status[0] + status.slice(1).toLowerCase() : '-');
  return <span className={`badge ${STATUS_COLOR[status] || ''}`}>{label}</span>;
}

export function DepartmentCell({ doc }) {
  if (doc.department) return doc.department;
  if (doc.routing && doc.routing.pending_review) return <span className="badge amber">Pending review</span>;
  if (doc.status === 'REJECTED') return <span className="muted">none</span>;
  return <span className="muted">-</span>;
}
