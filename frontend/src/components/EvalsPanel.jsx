import { useEffect, useState } from 'react';
import { api } from '../api';

// The latest report written by: python -m scripts.run_evals --answers
export default function EvalsPanel() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { api.evals().then(setReport).catch((e) => setError(e.message)); }, []);

  if (error) return <section className="card"><p className="muted">{error}</p></section>;
  if (!report) return null;
  return (
    <section className="card">
      <h2>Eval report</h2>
      <p className="muted">
        Provider <strong>{report.provider}</strong> ({report.model}) · {report.documents} documents ·{' '}
        {report.questions} questions ({report.refusal_questions} must be refused) · generated {report.generated_at}
      </p>
      {report.provider === 'offline' && (
        <p className="badge amber">
          Offline rules, not an LLM. The rules were written against these same documents, so these numbers
          test the pipeline and the harness, not model quality.
        </p>
      )}
      {report.tables.map((t) => (
        <div key={t.title}>
          <h3>{t.title}</h3>
          <table>
            <thead><tr>{t.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{t.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{String(v)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
