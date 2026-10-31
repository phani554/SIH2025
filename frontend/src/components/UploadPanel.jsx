import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload } from 'lucide-react';
import { api } from '../api';

// Manual upload: the one input source. Every upload, accepted or rejected, has a trace.
export default function UploadPanel({ onUploaded, onShowRun }) {
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);

  const onDrop = async (files) => {
    setBusy(true);
    for (const file of files) {
      try {
        const res = await api.upload(file);
        setResults((prev) => [{ name: file.name, ...res }, ...prev]);
      } catch (err) {
        setResults((prev) => [{ name: file.name, error: err.message, run_id: err.runId }, ...prev]);
      }
    }
    setBusy(false);
    onUploaded();
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  return (
    <section className="card">
      <h2>Upload documents</h2>
      <div {...getRootProps({ className: `dropzone ${isDragActive ? 'active' : ''}` })}>
        <input {...getInputProps()} />
        <Upload size={32} />
        <p>{busy ? 'Processing…' : 'Drop PDF, image or text files here, or click to choose'}</p>
      </div>
      <ul className="upload-results">
        {results.map((r, i) => (
          <li key={i} className="row">
            <span>
              <strong>{r.name}</strong>{' '}
              {r.error ? <span className="badge red">rejected: {r.error}</span>
                : r.duplicate ? <span className="badge grey">duplicate of #{r.doc_id}</span>
                : <span className={`badge ${r.status === 'NEEDS_REVIEW' ? 'amber' : 'green'}`}>{r.status}</span>}
            </span>
            {r.run_id && <button className="link" onClick={() => onShowRun(r.run_id)}>Show me how</button>}
          </li>
        ))}
      </ul>
    </section>
  );
}
