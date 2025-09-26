import { useState } from 'react'
import { FileText, Shield, Clock, Users, Zap } from 'lucide-react'
import FileUpload from './components/FileUpload'
import ProcessingStatus from './components/ProcessingStatus'
import ResultDisplay from './components/ResultDisplay'
import { extractTextFromFile, processWithGemini } from './utils/documentProcessor'
import './App.css'

function App() {
  const [uploadedFile, setUploadedFile] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [processingStage, setProcessingStage] = useState('')
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [extractedText, setExtractedText] = useState('')

  const handleFileSelect = (file) => {
    setUploadedFile(file)
    setResult(null)
    setError(null)
    setExtractedText('')
  }

  const processDocument = async () => {
    if (!uploadedFile) return
    
    setProcessing(true)
    setError(null)
    setProgress(0)
    
    try {
      // Stage 1: Extract text
      setProcessingStage('extracting')
      setProgress(10)
      
      const text = await extractTextFromFile(uploadedFile)
      setExtractedText(text)
      
      if (!text || text.trim().length < 5) {
        throw new Error('Could not extract sufficient text from document. Please ensure the document contains readable text.')
      }
      
      // Stage 2: AI Analysis with progress callback
      const onProgress = (stage, progress) => {
        setProcessingStage(stage)
        setProgress(progress)
      }
      
      const analysisResult = await processWithGemini(
        text, 
        uploadedFile.name, 
        uploadedFile.type,
        onProgress
      )
      
      // Stage 5: Finalize
      setProcessingStage('finalizing')
      setProgress(100)
      
      setTimeout(() => {
        setResult(analysisResult)
        setProcessing(false)
        setProcessingStage('')
        setProgress(0)
      }, 500)
      
    } catch (err) {
      console.error('Processing error:', err)
      setError(err.message || 'Failed to process document')
      setProcessing(false)
      setProcessingStage('')
      setProgress(0)
    }
  }

  const handleNotify = () => {
    // Simulate notification
    alert(`Notification sent to ${result.department} department and key personnel: ${result.keyPersons?.join(', ')}`)
  }

  const handleDownload = () => {
    // Create a beautiful HTML report
    const reportHTML = generateHTMLReport(result, uploadedFile.name, extractedText);
    
    const blob = new Blob([reportHTML], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `KMRL_Analysis_Report_${uploadedFile.name.split('.')[0]}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const handleAnalyzeAgain = () => {
    setResult(null);
    setError(null);
    setExtractedText('');
    setUploadedFile(null);
  }

  const generateHTMLReport = (analysis, fileName, extractedText) => {
    return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KMRL Document Analysis Report</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            color: #1f2937;
            line-height: 1.6;
            padding: 20px;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { 
            background: linear-gradient(135deg, #3b82f6, #60a5fa);
            color: white;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 10px 25px rgba(59, 130, 246, 0.3);
        }
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; font-weight: 800; }
        .header p { font-size: 1.2rem; opacity: 0.9; }
        .report-meta { 
            background: white;
            padding: 25px;
            border-radius: 16px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border-left: 4px solid #3b82f6;
        }
        .section { 
            background: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .section h2 { 
            color: #3b82f6;
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #dbeafe;
        }
        .department-badge { 
            background: linear-gradient(135deg, #3b82f6, #60a5fa);
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            font-weight: 700;
            display: inline-block;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .urgency { 
            padding: 8px 16px;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 15px;
        }
        .urgency.critical { background: #fef2f2; color: #dc2626; }
        .urgency.high { background: #fef3c7; color: #d97706; }
        .urgency.medium { background: #f0f9ff; color: #0284c7; }
        .urgency.low { background: #f0fdf4; color: #059669; }
        .key-points { list-style: none; }
        .key-points li { 
            background: #f8fafc;
            padding: 12px 16px;
            margin-bottom: 8px;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
        }
        .action-item { 
            background: #f9fafb;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            border-left: 4px solid #10b981;
        }
        .priority { 
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .priority.high { background: #fef2f2; color: #dc2626; }
        .priority.medium { background: #fef3c7; color: #d97706; }
        .priority.low { background: #f0fdf4; color: #059669; }
        .footer { 
            text-align: center;
            padding: 30px;
            color: #6b7280;
            font-size: 0.9rem;
        }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 KMRL Document Analysis Report</h1>
            <p>AI-Powered Document Intelligence System</p>
        </div>

        <div class="report-meta">
            <h3>📄 Document Information</h3>
            <p><strong>File Name:</strong> ${fileName}</p>
            <p><strong>Document Type:</strong> ${analysis.documentType || 'N/A'}</p>
            <p><strong>Processed At:</strong> ${new Date().toLocaleString()}</p>
            <p><strong>Analysis Confidence:</strong> ${analysis.confidence || 'High'}</p>
        </div>

        <div class="section">
            <h2>🏢 Department Classification</h2>
            <div class="department-badge">${analysis.department || 'General'}</div>
            <p><strong>Reasoning:</strong> ${analysis.reasoning || 'Based on document content analysis'}</p>
            ${analysis.keywords ? `<p><strong>Key Terms:</strong> ${analysis.keywords.join(', ')}</p>` : ''}
        </div>

        <div class="section">
            <h2>📝 Document Summary</h2>
            <h4>Overview</h4>
            <p>${analysis.overview || 'Document analysis completed'}</p>
            
            <h4>Detailed Summary</h4>
            <p>${analysis.detailedSummary || analysis.summary || 'Comprehensive analysis of the document content'}</p>
            
            ${analysis.keyPoints ? `
            <h4>Key Points</h4>
            <ul class="key-points">
                ${analysis.keyPoints.map(point => `<li>${point}</li>`).join('')}
            </ul>
            ` : ''}
        </div>

        <div class="section">
            <h2>🎯 Purpose & Actions</h2>
            <h4>Primary Purpose</h4>
            <p>${analysis.primaryPurpose || analysis.purpose || 'Document processing and analysis'}</p>
            
            <div class="urgency ${(analysis.urgencyLevel || analysis.urgency || 'medium').toLowerCase()}">
                Urgency: ${analysis.urgencyLevel || analysis.urgency || 'Medium'}
            </div>
            
            ${analysis.urgencyReason ? `<p><strong>Urgency Reasoning:</strong> ${analysis.urgencyReason}</p>` : ''}
            
            ${analysis.actionItems ? `
            <h4>Required Actions</h4>
            ${analysis.actionItems.map(item => `
                <div class="action-item">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                        <span style="font-weight: 600;">${typeof item === 'string' ? item : item.action}</span>
                        ${typeof item === 'object' && item.priority ? `<span class="priority ${item.priority.toLowerCase()}">${item.priority}</span>` : ''}
                    </div>
                    ${typeof item === 'object' ? `
                        <p><strong>Responsible:</strong> ${item.responsible || 'Not specified'}</p>
                        ${item.timeframe ? `<p><strong>Timeframe:</strong> ${item.timeframe}</p>` : ''}
                    ` : ''}
                </div>
            `).join('')}
            ` : ''}
        </div>

        <div class="grid">
            <div class="section">
                <h2>📅 Timeline & Details</h2>
                <p><strong>Deadline:</strong> ${analysis.deadline || 'No deadline mentioned'}</p>
                <p><strong>Key Persons:</strong> ${analysis.keyPersons ? analysis.keyPersons.join(', ') : 'Not specified'}</p>
                <p><strong>Location:</strong> ${analysis.locations ? analysis.locations.join(', ') : analysis.location || 'Not specified'}</p>
            </div>

            <div class="section">
                <h2>⚠️ Risk & Compliance</h2>
                <p><strong>Risk Level:</strong> ${analysis.riskLevel || 'Medium'}</p>
                <p><strong>Compliance Required:</strong> ${analysis.complianceRequired || 'Not specified'}</p>
                <p><strong>Estimated Cost:</strong> ${analysis.estimatedCost || 'No cost mentioned'}</p>
            </div>
        </div>

        ${analysis.technicalDetails && analysis.technicalDetails !== 'None mentioned' ? `
        <div class="section">
            <h2>🔧 Technical Details</h2>
            <p>${analysis.technicalDetails}</p>
        </div>
        ` : ''}

        <div class="footer">
            <p>Generated by KMRL Document Intelligence System</p>
            <p>Powered by Gemini AI | ${new Date().toLocaleDateString()}</p>
        </div>
    </div>
</body>
</html>`;
  }

  const handleShare = () => {
    // Simulate sharing functionality
    const shareText = `KMRL Document Analysis:\nDepartment: ${result.department}\nUrgency: ${result.urgency}\nSummary: ${result.summary}`
    
    if (navigator.share) {
      navigator.share({
        title: 'KMRL Document Analysis',
        text: shareText
      })
    } else {
      navigator.clipboard.writeText(shareText)
      alert('Analysis copied to clipboard!')
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo-section">
            <div className="logo">
              <Zap size={32} />
            </div>
            <div className="title-section">
              <h1>KMRL Document Intelligence</h1>
              <p>AI-Powered Document Classification & Analysis System</p>
            </div>
          </div>
          
          <div className="stats-section">
            <div className="stat">
              <Shield size={20} />
              <div>
                <span className="stat-number">99.9%</span>
                <span className="stat-label">AI Accuracy</span>
              </div>
            </div>
            <div className="stat">
              <Clock size={20} />
              <div>
                <span className="stat-number">&lt;60s</span>
                <span className="stat-label">Analysis Time</span>
              </div>
            </div>
            <div className="stat">
              <Users size={20} />
              <div>
                <span className="stat-number">8+</span>
                <span className="stat-label">Departments</span>
              </div>
            </div>
            <div className="stat">
              <FileText size={20} />
              <div>
                <span className="stat-number">15+</span>
                <span className="stat-label">File Types</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="main-content">
        {!processing && !result && (
          <div className="upload-section">
            <FileUpload 
              onFileSelect={handleFileSelect} 
              selectedFile={uploadedFile}
            />
            
            {uploadedFile && (
              <div className="process-section">
                <button 
                  onClick={processDocument} 
                  className="process-btn"
                  disabled={processing}
                >
                  <Zap size={20} />
                  {processing ? 'Analyzing...' : 'Analyze with AI'}
                </button>
                <p className="process-description">
                  Our advanced AI will extract text, classify the document, identify the purpose, 
                  assess urgency, and route it to the appropriate KMRL department with detailed analysis.
                </p>
              </div>
            )}
          </div>
        )}

        {processing && (
          <ProcessingStatus 
            stage={processingStage} 
            progress={progress}
          />
        )}

        {error && (
          <div className="error-section">
            <div className="error-card">
              <h3>Processing Error</h3>
              <p>{error}</p>
              <button 
                onClick={() => setError(null)} 
                className="retry-btn"
              >
                Try Again
              </button>
            </div>
          </div>
        )}

        {result && (
          <ResultDisplay 
            result={result}
            fileName={uploadedFile.name}
            onNotify={handleNotify}
            onDownload={handleDownload}
            onShare={handleShare}
            onAnalyzeAgain={handleAnalyzeAgain}
          />
        )}
      </main>

      <footer className="footer">
        <p>© 2025 KMRL Document Intelligence System | Powered by Gemini AI</p>
      </footer>
    </div>
  )
}

export default App
