import { useEffect, useState } from 'react';
import { api, DEPARTMENTS } from '../api';

// Human-in-the-loop: low-confidence or critical documents wait here.
export default function ReviewPanel({ refreshKey, onChange }) {
  const [queue, setQueue] = useState([]);
  const [audit, setAudit] = useState([]);
  const [choice, setChoice] = useState({});

  useEffect(() => {
    api.listDocuments({ status: 'NEEDS_REVIEW' }).then(setQueue).catch(() => setQueue([]));
    api.audit().then(setAudit).catch(() => setAudit([]));
  }, [refreshKey]);

  const approve = async (doc) => {
    await api.review(doc.doc_id, choice[doc.doc_id] || doc.department || null);
    onChange();
  };

  return (
    <div className="split">
      <section className="card">
        <h2>Review queue ({queue.length})</h2>
        {queue.length === 0 && <p className="muted">Nothing waiting for review.</p>}
        {queue.map((d) => (
          <div key={d.doc_id} className="row review-item">
            <span>#{d.doc_id} {d.file_name} <span className="muted">({d.urgency || '?'}, {d.confidence != null ? Math.round(d.confidence * 100) + '%' : 'no analysis'})</span></span>
            <select value={choice[d.doc_id] || d.department || ''}
              onChange={(e) => setChoice({ ...choice, [d.doc_id]: e.target.value })}>
              <option value="" disabled>Department</option>
              {DEPARTMENTS.map((x) => <option key={x}>{x}</option>)}
            </select>
            <button onClick={() => approve(d)}>Approve</button>
          </div>
        ))}
      </section>
      <section className="card">
        <h2>Audit trail</h2>
        <table>
          <thead><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Doc</th></tr></thead>
          <tbody>
            {audit.map((r) => (
              <tr key={r.audit_id}><td>{r.at}</td><td>{r.actor}</td><td>{r.action}</td><td>{r.doc_id ?? '-'}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
