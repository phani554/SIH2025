import { useEffect, useState } from 'react';
import { api, DEPARTMENTS } from '../api';

export default function DocumentList({ refreshKey }) {
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
      {selected && <DocumentDetail doc={selected} />}
    </div>
  );
}

function DocumentDetail({ doc }) {
  const a = doc.analysis;
  return (
    <section className="card detail">
      <h2>{doc.file_name}</h2>
      <p className="muted">
        {doc.doc_type} · {doc.departments.map((d) => d.name).join(', ')} · confidence{' '}
        {doc.confidence != null ? Math.round(doc.confidence * 100) + '%' : '-'} · {doc.chunks.length} chunks
      </p>
      <button className="link" onClick={() => api.openFile(doc.doc_id)}>Open original file</button>
      {a ? (
        <>
          <h3>Summary</h3><p>{a.summary}</p>
          <h3>Why this department</h3><p>{a.reasoning}</p>
          {a.key_points.length > 0 && (<><h3>Key points</h3><ul>{a.key_points.map((k, i) => <li key={i}>{k}</li>)}</ul></>)}
          {doc.action_items.length > 0 && (
            <><h3>Action items</h3>
              <ul>{doc.action_items.map((x, i) => (
                <li key={i}>{x.action} <span className="muted">({x.owner || 'unassigned'}, {x.priority}{x.due ? `, due ${x.due}` : ''})</span></li>
              ))}</ul></>
          )}
          {a.amounts.length > 0 && <p><strong>Amounts:</strong> {a.amounts.join(', ')}</p>}
          {a.deadline && <p><strong>Deadline:</strong> {a.deadline}</p>}
        </>
      ) : <p className="muted">No analysis yet. This document is waiting for human review.</p>}
      <h3>Chunks</h3>
      {doc.chunks.map((c) => (
        <p key={c.chunk_no} className="chunk">
          <span className="muted">#{c.chunk_no} p.{c.page}</span>{' '}
          {c.flagged ? <span className="badge red">possible prompt injection, excluded</span> : null} {c.preview}…
        </p>
      ))}
    </section>
  );
}
