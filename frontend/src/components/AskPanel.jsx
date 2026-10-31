import { useState } from 'react';
import { api, DEPARTMENTS } from '../api';

// RAG chat: every answer shows the exact chunks it was built from.
export default function AskPanel({ onShowRun }) {
  const [question, setQuestion] = useState('');
  const [department, setDepartment] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [useHyde, setUseHyde] = useState(true);
  const [mode, setMode] = useState('hybrid');

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try { setResult(await api.ask(question, department, useHyde, mode)); }
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
      <div className="row options">
        <label>Retrieval{' '}
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="hybrid">Hybrid (BM25 + vector)</option>
            <option value="keyword">Keyword only</option>
            <option value="vector">Vector only</option>
          </select>
        </label>
        <label><input type="checkbox" checked={useHyde} onChange={(e) => setUseHyde(e.target.checked)} /> HyDE</label>
      </div>
      {error && <p className="badge red">{error}</p>}
      {result && (
        <div className="answer">
          <div className="row">
            <p className={result.grounded ? '' : 'muted'}>{result.answer}</p>
            {result.run_id && <button onClick={() => onShowRun(result.run_id)}>Show me how</button>}
          </div>
          {result.grounded && (
            <p className="muted">Faithfulness: {Math.round(result.faithfulness * 100)}% of sentences backed by their source</p>
          )}
          {result.citations.map((c) => (
            <div key={c.n} className="citation">
              <strong>[{c.n}]</strong> {c.file_name}{c.page ? `, p.${c.page}` : ''}{' '}
              <span className={`badge ${c.supported ? 'green' : 'amber'}`}>{c.supported ? 'verified' : 'weak support'}</span>{' '}
              <button className="link" onClick={() => api.openFile(c.doc_id)}>open</button>
              <p className="muted">{c.snippet}…</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
