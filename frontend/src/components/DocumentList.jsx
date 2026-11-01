import { useEffect, useState } from 'react';
import { api, DEPARTMENTS } from '../api';
import Routing from './Routing';
import { DepartmentCell, StatusBadge } from './Status';

export default function DocumentList({ refreshKey, onShowRun }) {
  const [docs, setDocs] = useState([]);
  const [department, setDepartment] = useState('');
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [definitions, setDefinitions] = useState(null);

  useEffect(() => { api.departments().then(setDefinitions).catch(() => setDefinitions(null)); }, []);

  useEffect(() => {
    api.listDocuments(department ? { department } : {}).then(setDocs).catch(() => setDocs([]));
  }, [department, refreshKey]);

  const open = async (id) => {
    setError('');
    try { setSelected(await api.getDocument(id)); } catch (e) { setError(e.message); }
  };

  return (
    <div className="split">
      <section className="card">
        <div className="row">
          <h2>Documents</h2>
          <select value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">All departments</option>
            {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>
        <table className="doc-table">
          <thead><tr><th>#</th><th>File</th><th>Department</th><th>Urgency</th><th>Status</th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.doc_id} onClick={() => open(d.doc_id)} className="clickable">
                <td>{d.doc_id}</td><td>{d.file_name}</td><td><DepartmentCell doc={d} /></td>
                <td>{d.urgency || '-'}</td><td><StatusBadge status={d.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {error && <p className="badge red">{error}</p>}
        {definitions && (
          <details className="definitions">
            <summary>What each department owns</summary>
            <p className="small"><strong>Rule:</strong> {definitions.rule}</p>
            <table className="small">
              <tbody>
                {definitions.departments.map((d) => (
                  <tr key={d.name}><th>{d.name}</th><td>{d.owns} <span className="muted">Not: {d.not}</span></td></tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
      </section>
      {selected && <DocumentDetail doc={selected} onShowRun={onShowRun} />}
    </div>
  );
}

function DocumentDetail({ doc, onShowRun }) {
  const l1 = doc.level1;
  const l2 = doc.level2;
  return (
    <section className="card detail">
      <div className="row">
        <h2>{doc.file_name}</h2>
        {doc.runs.length > 0 && <button onClick={() => onShowRun(doc.runs[doc.runs.length - 1].run_id)}>Show me how</button>}
      </div>
      <p className="muted">
        {doc.doc_type || 'unknown type'} · {doc.departments.length ? doc.departments.map((d) => d.name).join(', ')
          : (doc.routing && doc.routing.pending_review ? 'department pending review' : 'no department')} ·
        confidence {doc.confidence != null ? Math.round(doc.confidence * 100) + '%' : '-'} · {doc.chunks.length} chunks ·{' '}
        <StatusBadge status={doc.status} />
      </p>
      {doc.status === 'NEEDS_REVIEW' && doc.review_reasons.length > 0 && (
        <p className="badge amber">Held for review: {doc.review_reasons.join('; ')}</p>
      )}
      {/* The original is unmasked, so only admins and reviewers may open it (the server enforces this too). */}
      <button className="link" onClick={() => api.openFile(doc.doc_id).catch((e) => alert(e.message))}>
        Open original file (admins and reviewers)
      </button>
      {doc.routing && (<><h3>Department routing</h3><Routing routing={doc.routing} /></>)}
      {l1 && (
        <>
          <h3>Level 1 · preliminary analysis</h3>
          <p>{l1.summary}</p>
          <p className="muted small">Urgency {l1.urgency} · {l1.language} · {l1.reasoning}</p>
        </>
      )}
      {l2 && (
        <>
          <h3>Level 2 · extracted facts</h3>
          <table className="small">
            <tbody>
              {['dates', 'amounts', 'reference_ids', 'vendors'].map((k) => (
                <tr key={k}><th>{k.replace('_', ' ')}</th>
                  <td>{l2[k].length ? l2[k].map((e) => `${e.value} (${Math.round(e.confidence * 100)}%)`).join(', ') : '-'}</td></tr>
              ))}
              <tr><th>deadline</th><td>{l2.deadline || '-'}</td></tr>
            </tbody>
          </table>
        </>
      )}
      {doc.action_items.length === 0 && l2 && l2.action_items.length > 0 && doc.routing && doc.routing.pending_review && (
        <p className="muted small">{l2.action_items.length} action item(s) held until a reviewer picks the department.</p>
      )}
      {doc.action_items.length > 0 && (
        <><h3>Action items</h3>
          <ul>{doc.action_items.map((x, i) => (
            <li key={i}>{x.action} <span className="muted">({x.priority}{x.due ? `, due ${x.due}` : ''})</span></li>
          ))}</ul></>
      )}
      <h3>Chunks (as indexed, after redaction)</h3>
      {doc.chunks.map((c) => (
        <p key={c.chunk_no} className="chunk"><span className="muted">#{c.chunk_no} p.{c.page}</span> {c.preview}…</p>
      ))}
    </section>
  );
}
