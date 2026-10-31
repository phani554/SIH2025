// Department routing, shown the same way in the document detail and in Show me how:
// the final department, the per-chunk signals, any chunk that disagrees, and the Decisions API check.
export default function Routing({ routing }) {
  if (!routing) return null;
  const decisions = routing.decisions;
  const top = decisions ? decisions.probabilities.slice(0, 3) : [];
  return (
    <div className="routing">
      <p>
        <strong>Department:</strong> <span className="badge green">{routing.final_department}</span>{' '}
        {routing.agrees_with_chunks
          ? <span className="muted small">all chunks agree</span>
          : <span className="badge amber">chunk and document disagree</span>}
      </p>
      {!routing.agrees_with_chunks && (
        <div className="callout">
          {routing.disagreements.map((d) => (
            <p key={d.chunk_no} className="small">
              Chunk #{d.chunk_no} looks like <strong>{d.chunk_says}</strong> ({d.matched}) → document is{' '}
              <strong>{d.document_says}</strong>
            </p>
          ))}
          <p className="small">
            <strong>Why {routing.final_department}:</strong> {routing.reason}
          </p>
        </div>
      )}
      {decisions && (
        <p className="small">
          <strong>Decisions API:</strong>{' '}
          {top.map((p) => (
            <span key={p.value} className={`badge ${p.value === routing.final_department ? 'green' : ''}`}>
              {p.value} {Math.round(p.probability * 100)}%
            </span>
          ))}{' '}
          <span className={routing.review_reason ? 'badge red' : 'muted'}>{routing.decisions_check}</span>
        </p>
      )}
      <p className="muted small">
        Chunk votes: {Object.entries(routing.chunk_votes).map(([d, n]) => `${d} ${n}`).join(', ') || 'none'}
      </p>
    </div>
  );
}
