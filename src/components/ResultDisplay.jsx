import React from 'react';
import { 
  Building2, 
  FileText, 
  Target, 
  AlertTriangle, 
  CheckSquare, 
  Users, 
  Calendar, 
  Tag, 
  Shield, 
  DollarSign, 
  MapPin,
  Download,
  Share2,
  Bell
} from 'lucide-react';
import { getDepartmentColor, getUrgencyColor } from '../utils/documentProcessor';

const ResultDisplay = ({ result, fileName, onNotify, onDownload, onShare, onAnalyzeAgain }) => {
  const departmentColor = getDepartmentColor(result.department);
  const urgencyColor = getUrgencyColor(result.urgencyLevel);

  return (
    <div className="result-display">
      <div className="result-header">
        <div className="result-title">
          <FileText size={24} />
          <h2>KMRL Document Analysis Complete</h2>
          <div className="confidence-badge">
            Confidence: {result.confidence}
          </div>
        </div>
        <div className="result-actions">
          <button className="action-btn analyze-again" onClick={onAnalyzeAgain}>
            <FileText size={16} />
            Analyze Again
          </button>
          <button className="action-btn notify" onClick={onNotify}>
            <Bell size={16} />
            Notify {result.department}
          </button>
          <button className="action-btn share" onClick={onShare}>
            <Share2 size={16} />
            Share Analysis
          </button>
          <button className="action-btn download" onClick={onDownload}>
            <Download size={16} />
            Download Report
          </button>
        </div>
      </div>

      <div className="result-grid">
        {/* Department Classification */}
        <div className="result-card primary">
          <div className="card-header">
            <Building2 size={20} />
            <h3>Department Classification</h3>
          </div>
          <div className="department-badge" style={{ backgroundColor: departmentColor }}>
            {result.department}
          </div>
          <div className={`urgency-indicator classifier ${result.urgencyLevel?.toLowerCase() || result.urgency?.toLowerCase() || 'medium'}`}>
            <AlertTriangle size={16} />
            <span>{result.urgencyLevel || result.urgency || 'Medium'} Priority</span>
          </div>
        </div>

        {/* Document Analysis */}
        <div className="result-card summary">
          <div className="card-header">
            <FileText size={20} />
            <h3>Document Analysis</h3>
          </div>
          <div className="summary-content">
            <div className="overview">
              <h4>Overview</h4>
              <p>{result.overview}</p>
            </div>
            <div className="detailed-summary">
              <h4>Detailed Summary</h4>
              <p>{result.detailedSummary}</p>
            </div>
            <div className="key-points">
              <h4>Key Points</h4>
              <ul>
                {result.keyPoints?.map((point, index) => (
                  <li key={index}>{point}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="document-meta">
            <span className="doc-type">{result.documentType}</span>
            <span className="file-name">{fileName}</span>
            <span className="source">{result.documentSource}</span>
          </div>
        </div>

        {/* Purpose & Actions */}
        <div className="result-card purpose">
          <div className="card-header">
            <Target size={20} />
            <h3>Purpose & Actions</h3>
          </div>
          <div className="purpose-content">
            <div className="primary-purpose">
              <h4>Primary Purpose</h4>
              <p>{result.primaryPurpose}</p>
            </div>
            
            {result.secondaryPurposes && result.secondaryPurposes.length > 0 && (
              <div className="secondary-purposes">
                <h4>Secondary Purposes</h4>
                <ul>
                  {result.secondaryPurposes.map((purpose, index) => (
                    <li key={index}>{purpose}</li>
                  ))}
                </ul>
              </div>
            )}
            
            <div className="urgency-section">
              <h4>Urgency Assessment</h4>
              <div className="urgency-indicator">
                <AlertTriangle size={16} style={{ color: urgencyColor }} />
                <span style={{ color: urgencyColor }}>{result.urgencyLevel}</span>
              </div>
              <p className="urgency-reason">{result.urgencyReason}</p>
            </div>
          </div>
          
          <div className="action-items">
            <h4><CheckSquare size={16} /> Required Actions:</h4>
            {result.actionItems?.map((item, index) => (
              <div key={index} className="action-item">
                <div className="action-header">
                  <span className="action-text">{item.action}</span>
                  <span className={`priority-badge ${item.priority?.toLowerCase()}`}>
                    {item.priority}
                  </span>
                </div>
                <div className="action-details">
                  <span><strong>Responsible:</strong> {item.responsible}</span>
                  {item.timeframe && <span><strong>Timeframe:</strong> {item.timeframe}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Key Information */}
        <div className="result-card details">
          <div className="card-header">
            <Users size={20} />
            <h3>Key Information</h3>
          </div>
          
          <div className="detail-grid">
            <div className="detail-item">
              <Calendar size={16} />
              <div>
                <strong>Deadline:</strong>
                <span>{result.deadline}</span>
              </div>
            </div>
            
            <div className="detail-item">
              <Users size={16} />
              <div>
                <strong>Key Persons:</strong>
                <span>{result.keyPersons?.join(', ')}</span>
              </div>
            </div>
            
            <div className="detail-item">
              <MapPin size={16} />
              <div>
                <strong>Location:</strong>
                <span>{result.location}</span>
              </div>
            </div>
            
            <div className="detail-item">
              <DollarSign size={16} />
              <div>
                <strong>Cost Impact:</strong>
                <span>{result.estimatedCost}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Risk & Compliance */}
        <div className="result-card risk">
          <div className="card-header">
            <Shield size={20} />
            <h3>Risk & Compliance</h3>
          </div>
          
          <div className="risk-indicators">
            <div className="risk-item">
              <span className="risk-label">Risk Level:</span>
              <span className={`risk-badge ${result.riskLevel?.toLowerCase()}`}>
                {result.riskLevel}
              </span>
            </div>
            
            <div className="risk-item">
              <span className="risk-label">Compliance Required:</span>
              <span className={`compliance-badge ${result.complianceRequired === 'Yes' ? 'required' : 'not-required'}`}>
                {result.complianceRequired}
              </span>
            </div>
          </div>
        </div>

        {/* Compact section for Tags & Categories and Document Traceability */}
        <div className="result-grid-compact">
          {/* Tags & Categories */}
          <div className="result-card tags">
            <div className="card-header">
              <Tag size={20} />
              <h3>Tags & Categories</h3>
            </div>
            
            <div className="tag-list">
              {result.tags?.map((tag, index) => (
                <span key={index} className="tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* Document Traceability */}
          <div className="result-card traceability-card">
            <div className="card-header">
              <FileText size={20} />
              <h3>Document Traceability</h3>
            </div>
            
            <div className="trace-info-compact">
              <div className="trace-item">
                <strong>Original File:</strong>
                <span>{fileName}</span>
              </div>
              <div className="trace-item">
                <strong>Processed:</strong>
                <span>{new Date().toLocaleString()}</span>
              </div>
              <div className="trace-item">
                <strong>AI Model:</strong>
                <span>Gemini 2.5 Pro</span>
              </div>
              <div className="trace-item">
                <strong>Confidence:</strong>
                <span>High</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultDisplay;