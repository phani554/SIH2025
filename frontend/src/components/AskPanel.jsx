import { useState } from 'react';
import { api, DEPARTMENTS } from '../api';

// RAG chat: every answer shows the exact chunks it was built from.
export default function AskPanel() {
  const [question, setQuestion] = useState('');
  const [department, setDepartment] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { setResult(await api.ask(question, department)); }
    catch (err) { setError(err.message); }
    setBusy(false);
  };

  return (
    <section className="card">
      <h2>Ask the documents</h2>
      <form onSubmit={submit} className="row">
        <input value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. When is the Alstom invoice payment due?" />
        <select value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {DEPARTMENTS.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button disabled={busy || question.length < 3}>{busy ? 'Searching…' : 'Ask'}</button>
      </form>
      {error && <p className="badge red">{error}</p>}
      {result && (
        <div className="answer">
          <p className={result.grounded ? '' : 'muted'}>{result.answer}</p>
          {result.citations.map((c) => (
            <div key={c.n} className="citation">
              <strong>[{c.n}]</strong> {c.file_name}{c.page ? `, p.${c.page}` : ''}{' '}
              <a href={api.fileUrl(c.doc_id)} target="_blank" rel="noreferrer">open</a>
              <p className="muted">{c.snippet}…</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
