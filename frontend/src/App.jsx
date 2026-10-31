import { useEffect, useState } from 'react';
import { api, getKey, setKey } from './api';
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
  const [key, setKeyInput] = useState(getKey());
  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    api.health().then((h) => setProvider(h.llm_provider)).catch(() => setProvider('backend offline'));
  }, []);

  return (
    <div className="app">
      <header>
        <h1>MetroMind <span className="muted">· KMRL Document Intelligence</span></h1>
        <div className="row">
          <input type="password" className="key" placeholder="API key" value={key}
            onChange={(e) => { setKeyInput(e.target.value); setKey(e.target.value); }}
            onBlur={refresh} />
          <span className="badge">LLM: {provider}</span>
        </div>
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
