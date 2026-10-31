import { useEffect, useState } from 'react';
import { api } from './api';
import UploadPanel from './components/UploadPanel';
import DocumentList from './components/DocumentList';
import AskPanel from './components/AskPanel';
import ReviewPanel from './components/ReviewPanel';
import './App.css';

const TABS = ['Upload', 'Documents', 'Ask', 'Review & Audit'];

export default function App() {
  const [tab, setTab] = useState('Upload');
  const [refreshKey, setRefreshKey] = useState(0);
  const [provider, setProvider] = useState('…');
  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    api.health().then((h) => setProvider(h.llm_provider)).catch(() => setProvider('backend offline'));
  }, []);

  return (
    <div className="app">
      <header>
        <h1>MetroMind <span className="muted">· KMRL Document Intelligence</span></h1>
        <span className="badge">LLM: {provider}</span>
      </header>
      <nav>
        {TABS.map((t) => (
          <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </nav>
      <main>
        {tab === 'Upload' && <UploadPanel onUploaded={refresh} />}
        {tab === 'Documents' && <DocumentList refreshKey={refreshKey} />}
        {tab === 'Ask' && <AskPanel />}
        {tab === 'Review & Audit' && <ReviewPanel refreshKey={refreshKey} onChange={refresh} />}
      </main>
    </div>
  );
}
