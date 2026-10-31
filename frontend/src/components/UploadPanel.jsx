import { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload } from 'lucide-react';
import { api } from '../api';

// Drop files -> backend ingests each one (dedupe, extract, chunk, embed, analyse).
export default function UploadPanel({ onUploaded }) {
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);

  const onDrop = async (files) => {
    setBusy(true);
    for (const file of files) {
      try {
        const res = await api.upload(file);
        setResults((prev) => [{ name: file.name, ...res }, ...prev]);
      } catch (err) {
        setResults((prev) => [{ name: file.name, error: err.message }, ...prev]);
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
        <p>{busy ? 'Processing…' : 'Drop PDFs, scans or text files here, or click to choose'}</p>
      </div>
      <ul className="upload-results">
        {results.map((r, i) => (
          <li key={i}>
            <strong>{r.name}</strong>{' '}
            {r.error ? <span className="badge red">{r.error}</span>
              : r.duplicate ? <span className="badge grey">duplicate of #{r.doc_id}</span>
              : <span className={`badge ${r.status === 'NEEDS_REVIEW' ? 'amber' : 'green'}`}>{r.status}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
