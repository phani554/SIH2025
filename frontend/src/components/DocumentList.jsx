import { useEffect, useState } from 'react';
import { api, DEPARTMENTS } from '../api';

export default function DocumentList({ refreshKey, onShowRun }) {
  const [docs, setDocs] = useState([]);
  const [department, setDepartment] = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    api.listDocuments(department ? { department } : {}).then(setDocs).catch(() => setDocs([]));
  }, [department, refreshKey]);

  const open = async (id) => setSelected(await api.getDocument(id));

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
        <table>
          <thead><tr><th>#</th><th>File</th><th>Department</th><th>Urgency</th><th>Status</th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.doc_id} onClick={() => open(d.doc_id)} className="clickable">
                <td>{d.doc_id}</td><td>{d.file_name}</td><td>{d.department || '-'}</td>
                <td>{d.urgency || '-'}</td><td><span className="badge">{d.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
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
        {doc.doc_type || 'unknown type'} · {doc.departments.map((d) => d.name).join(', ') || 'no department'} ·
        confidence {doc.confidence != null ? Math.round(doc.confidence * 100) + '%' : '-'} · {doc.chunks.length} chunks ·{' '}
        <span className="badge">{doc.status}</span>
      </p>
      {doc.review_reasons.length > 0 && (
        <p className="badge amber">Held for review: {doc.review_reasons.join('; ')}</p>
      )}
      <button className="link" onClick={() => api.openFile(doc.doc_id)}>Open original file</button>
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
