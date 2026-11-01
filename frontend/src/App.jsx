import { useEffect, useState } from 'react';
import { api, getKey, setKey } from './api';
import UploadPanel from './components/UploadPanel';
import DocumentList from './components/DocumentList';
import AskPanel from './components/AskPanel';
import ReviewPanel from './components/ReviewPanel';
import EvalsPanel from './components/EvalsPanel';
import ShowMeHow from './components/ShowMeHow';
import './App.css';

const TABS = ['Upload', 'Documents', 'Ask', 'Review & Audit', 'Evals'];

export default function App() {
  const [tab, setTab] = useState('Upload');
  const [refreshKey, setRefreshKey] = useState(0);
  const [provider, setProvider] = useState('…');
  const [key, setKeyInput] = useState(getKey());
  const [runId, setRunId] = useState(null);   // the run open in "Show me how"
  const refresh = () => setRefreshKey((k) => k + 1);

  useEffect(() => {
    api.health().then((h) => setProvider(`${h.llm_provider} · ${h.model}`)).catch(() => setProvider('backend offline'));
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
        {tab === 'Upload' && <UploadPanel onUploaded={refresh} onShowRun={setRunId} />}
        {tab === 'Documents' && <DocumentList refreshKey={refreshKey} onShowRun={setRunId} />}
        {tab === 'Ask' && <AskPanel onShowRun={setRunId} />}
        {tab === 'Review & Audit' && <ReviewPanel refreshKey={refreshKey} onChange={refresh} onShowRun={setRunId} />}
        {tab === 'Evals' && <EvalsPanel />}
      </main>
      {runId && <ShowMeHow runId={runId} onClose={() => setRunId(null)} />}
    </div>
  );
}
