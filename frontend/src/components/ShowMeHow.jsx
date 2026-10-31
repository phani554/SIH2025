import { useEffect, useState } from 'react';
import { api } from '../api';

// "Show me how": the trace of one run (an upload or a question), step by step.
// Top: the preliminary analysis (Level 1 + run plan). Below: one lane per layer, each step drawn
// in the lane of the layer that did it. Click a step to drill down.
const LAYERS = ['api', 'orchestrator', 'ingestion', 'knowledge', 'llm', 'actions'];
export default function ShowMeHow({ runId, onClose }) {
  const [run, setRun] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(null);

  useEffect(() => {
    api.run(runId).then(setRun).catch((e) => setError(e.message));
  }, [runId]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="row">
          <h2>Show me how · run #{runId}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {error && <p className="badge red">{error}</p>}
        {run && (
          <>
            <p className="muted">
              {run.kind === 'ingest' ? 'Upload' : 'Question'} by <strong>{run.actor}</strong> ({run.role}
              {run.department ? `, ${run.department}` : ''}) · {run.steps.length} steps · {run.duration_ms} ms ·{' '}
              <span className={`badge ${statusColour(run.status)}`}>{run.status}</span>
            </p>
            {run.summary && <p>{run.summary}</p>}
            {run.plan && <Preliminary kind={run.kind} plan={run.plan} steps={run.steps} />}
            <h3>Steps by layer</h3>
            <div className="lanes lane-head">
              {LAYERS.map((l) => <div key={l} className={`lane-title ${l}`}>{l}</div>)}
            </div>
            {run.steps.map((s) => (
              <div key={s.seq}>
                <div className="lanes">
                  {LAYERS.map((l) => (
                    <div key={l} className="lane">
                      {s.layer === l && (
                        <button className={`step-box ${l} ${s.status} ${open === s.seq ? 'open' : ''}`}
                          onClick={() => setOpen(open === s.seq ? null : s.seq)}>
                          <span className="small muted">{s.seq}.</span> {s.name}
                          <span className={`badge ${statusColour(s.status)}`}>{s.status}</span>
                          <span className="small muted">{s.duration_ms} ms</span>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {open === s.seq && (
                  <div className="step-detail">
                    {s.input_summary && <div className="small"><strong>in:</strong> {s.input_summary}</div>}
                    {s.output_summary && <div className="small"><strong>out:</strong> {s.output_summary}</div>}
                    <Detail detail={s.detail} />
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </aside>
    </div>
  );
}

function Preliminary({ kind, plan, steps }) {
  const l1 = plan.level1;
  const ran = new Set(steps.filter((s) => s.status !== 'skipped').map((s) => s.name.split(' ')[0]));
  return (
    <div className="prelim">
      {kind === 'ingest' && <h3>Preliminary analysis (Level 1)</h3>}
      {kind !== 'ingest' ? null : l1 ? (
        <>
          <p>
            {l1.departments.map((d, i) => (
              <span key={d.name} className={`badge ${i === 0 ? 'green' : ''}`}>
                {d.name} {Math.round(d.confidence * 100)}%
              </span>
            ))}{' '}
            · {l1.doc_type} · urgency <strong>{l1.urgency}</strong> · {l1.language}
          </p>
          <p><strong>L1 summary:</strong> {l1.summary}</p>
          <p className="muted small">Why: {l1.reasoning}</p>
        </>
      ) : <p className="muted">Level 1 did not run or did not pass validation.</p>}
      <h3>Run plan</h3>
      <p className="small">
        {plan.plan.max_steps && <>max steps <strong>{plan.plan.max_steps}</strong> · </>}
        max LLM calls <strong>{plan.plan.max_llm_calls}</strong> · max retries <strong>{plan.plan.max_retries}</strong>
        {plan.plan.mode && <> · mode {plan.plan.mode}, HyDE {plan.plan.hyde ? 'on' : 'off'}, top {plan.plan.top_k}</>}
        {plan.used && <> · used: {plan.used.steps_run} steps, {plan.used.llm_calls} LLM calls</>}
      </p>
      <p className="plan">
        {plan.plan.steps.map((name, i) => (
          <span key={name} className={`badge ${ran.has(name) ? 'green' : 'grey'}`}>{i + 1}. {name}</span>
        ))}
      </p>
    </div>
  );
}

// Generic drill-down: tables for lists of rows, code blocks for prompts and JSON, text otherwise.
function Detail({ detail }) {
  const entries = Object.entries(detail || {});
  if (!entries.length) return <p className="muted small">No extra detail for this step.</p>;
  return (
    <div className="detail-box">
      {entries.map(([key, value]) => (
        <div key={key} className="detail-item">
          <div className="detail-key">{key.replaceAll('_', ' ')}</div>
          <Value value={value} />
        </div>
      ))}
    </div>
  );
}

function Value({ value }) {
  if (value === null || value === undefined) return <span className="muted">none</span>;
  if (Array.isArray(value) && value.length && typeof value[0] === 'object') {
    const cols = Object.keys(value[0]);
    return (
      <table className="small">
        <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {value.map((row, i) => (
            <tr key={i}>{cols.map((c) => <td key={c}>{format(row[c])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    );
  }
  if (Array.isArray(value)) return <span>{value.length ? value.map(format).join(', ') : 'none'}</span>;
  if (typeof value === 'object') return <pre>{JSON.stringify(value, null, 2)}</pre>;
  if (typeof value === 'string' && (value.length > 120 || value.includes('\n'))) return <pre>{value}</pre>;
  return <span>{format(value)}</span>;
}

const format = (v) => (typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v));

const statusColour = (s) =>
  ({ ok: 'green', ANALYZED: 'green', ANSWERED: 'green', APPROVED: 'green', retried: 'amber',
     NEEDS_REVIEW: 'amber', DUPLICATE: 'grey', skipped: 'grey', REFUSED: 'grey',
     failed: 'red', REJECTED: 'red', FAILED: 'red' }[s] || '');
