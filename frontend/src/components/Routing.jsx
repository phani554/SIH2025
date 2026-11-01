// Department routing, shown the same way in the document detail and in Show me how:
// the final department (or "pending review" when the system was unsure), the per-chunk signals,
// any chunk that disagrees, the Decisions API check, and the reviewer's decision if there is one.
export default function Routing({ routing }) {
  if (!routing) return null;
  const decisions = routing.decisions;
  const top = decisions ? decisions.probabilities.slice(0, 3) : [];
  const final = routing.final_department;
  const pending = routing.pending_review && !final;
  const votes = Object.entries(routing.chunk_votes || {});
  return (
    <div className="routing">
      <p>
        <strong>Department:</strong>{' '}
        {pending
          ? <span className="badge amber">Pending review</span>
          : <span className="badge green">{final}</span>}{' '}
        {routing.reviewed_by
          ? <span className="muted small">decided by reviewer {routing.reviewed_by}</span>
          : votes.length === 0
            ? <span className="muted small">no chunk had department keywords</span>
            : routing.agrees_with_chunks
              ? <span className="muted small">all chunk signals agree</span>
              : <span className="badge amber">a chunk points elsewhere</span>}
      </p>

      {pending && (
        <div className="callout">
          <p className="small"><strong>Not decided automatically.</strong> {routing.review_reason}.</p>
          <p className="small">
            A reviewer picks between {routing.candidates.map((c, i) => (
              <span key={c}>{i > 0 && ' or '}<strong>{c}</strong></span>))}. Until then no department can open it
            and its action items are held.
          </p>
        </div>
      )}

      {routing.reviewer_note && <p className="small"><strong>Review:</strong> {routing.reviewer_note}.</p>}

      {!routing.agrees_with_chunks && (
        <div className="callout">
          {routing.disagreements.map((d) => (
            <p key={d.chunk_no} className="small">
              Chunk #{d.chunk_no} looks like <strong>{d.chunk_says}</strong> ({d.matched}) → Level 1 read the
              whole document as <strong>{d.document_says}</strong>
            </p>
          ))}
          <p className="small"><strong>Why {routing.level1_department || final}:</strong> {routing.reason}</p>
        </div>
      )}

      {decisions && (
        <p className="small">
          <strong>Decisions API:</strong>{' '}
          {top.map((p) => (
            <span key={p.value} className={`badge ${p.value === decisions.choice ? (routing.review_reason ? 'amber' : 'green') : ''}`}>
              {p.value} {Math.round(p.probability * 100)}%
            </span>
          ))}{' '}
          <span className={routing.review_reason ? 'badge red' : 'muted'}>{routing.decisions_check}</span>
        </p>
      )}
      <p className="muted small">
        Chunk votes: {votes.map(([d, n]) => `${d} ${n}`).join(', ') || 'none'}
      </p>
    </div>
  );
}
