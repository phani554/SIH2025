import { useEffect, useState } from 'react';
import { api, DEPARTMENTS } from '../api';
import { StatusBadge } from './Status';

// Human-in-the-loop: documents the system would not decide on alone wait here, with the reason.
// A pending document has NO department: the reviewer must pick one before it can be approved.
export default function ReviewPanel({ refreshKey, onChange, onShowRun }) {
  const [queue, setQueue] = useState([]);
  const [audit, setAudit] = useState([]);
  const [choice, setChoice] = useState({});
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.listDocuments({ status: 'NEEDS_REVIEW' }).then(setQueue).catch(() => setQueue([]));
    api.audit().then(setAudit).catch(() => setAudit([]));
    api.runs().then(setRuns).catch(() => setRuns([]));
  }, [refreshKey]);

  const lastRun = (docId) => runs.find((r) => r.doc_id === docId && r.kind === 'ingest');

  const decide = async (doc, approve) => {
    setError('');
    try {
      await api.review(doc.doc_id, approve ? (choice[doc.doc_id] || doc.department || null) : null, approve);
      onChange();
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="split">
      <section className="card">
        <h2>Review queue ({queue.length})</h2>
        {queue.length === 0 && <p className="muted">Nothing waiting for review.</p>}
        {error && <p className="badge red">{error}</p>}
        {queue.map((d) => {
          const pending = d.routing && d.routing.pending_review;
          const picked = choice[d.doc_id] || d.department || '';
          const run = lastRun(d.doc_id);
          return (
            <div key={d.doc_id} className="review-item">
              <div className="row">
                <strong>#{d.doc_id} {d.file_name}</strong>
                {run && <button className="link" onClick={() => onShowRun(run.run_id)}>Show me how</button>}
              </div>
              <p className="small">
                <span className="muted">Why it is here:</span> {d.review_reasons.join('; ') || 'flagged'}
              </p>
              {pending && (
                <p className="small">
                  <span className="muted">The system was unsure.</span> Level 1 said <strong>{d.routing.level1_department}</strong>;
                  Decisions API: {d.routing.top_probabilities.map((p) => (
                    <span key={p.value} className="badge">{p.value} {Math.round(p.probability * 100)}%</span>))}
                </p>
              )}
              <div className="row review-actions">
                <select aria-label="Department" value={picked}
                  onChange={(e) => setChoice({ ...choice, [d.doc_id]: e.target.value })}>
                  <option value="" disabled>{pending ? 'Pick a department' : 'Department'}</option>
                  {DEPARTMENTS.map((x) => <option key={x}>{x}</option>)}
                </select>
                <span className="row">
                  <button onClick={() => decide(d, true)} disabled={!picked}
                    title={!picked ? 'Pick a department first' : ''}>Approve</button>
                  <button className="secondary" onClick={() => decide(d, false)}>Reject</button>
                </span>
              </div>
            </div>
          );
        })}
      </section>
      <section className="card">
        <h2>Recent runs</h2>
        <table>
          <thead><tr><th>Run</th><th>Kind</th><th>Status</th><th>Summary</th><th></th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <td>#{r.run_id}</td><td>{r.kind}</td><td><StatusBadge status={r.status} /></td>
                <td className="small">{(r.summary || '').slice(0, 70)}</td>
                <td><button className="link" onClick={() => onShowRun(r.run_id)}>Show me how</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <h2>Audit trail</h2>
        <table>
          <thead><tr><th>Time (UTC)</th><th>Actor</th><th>Action</th><th>Doc</th><th>Detail</th></tr></thead>
          <tbody>
            {audit.map((r) => (
              <tr key={r.audit_id}>
                <td className="small">{r.at}</td><td>{r.actor}</td><td>{r.action}</td><td>{r.doc_id ?? '-'}</td>
                <td className="small">{(r.detail || '').slice(0, 90)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
