import { useState } from 'react';
import FileUploadZone from './FileUploadZone';
import ProcessedFilesList, { type ProcessedFile } from './ProcessedFilesList';
import DocumentSummary from './DocumentSummary';
import DepartmentAssignment from './DepartmentAssignment';
import Timeline from './Timeline';
import GraphVisualization from './GraphVisualization';
import ThemeToggle from './ThemeToggle';
import { addDays, subDays } from 'date-fns';

export default function Dashboard() {
  const [processedFiles, setProcessedFiles] = useState<ProcessedFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [aiSuggestion, setAiSuggestion] = useState<any>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const handleFilesUpload = async (files: File[]) => {
    console.log('Files uploaded:', files.map(f => f.name));
    setIsProcessing(true);
    setIsAnalyzing(true);

    // Add files to processing list
    const newFiles: ProcessedFile[] = files.map(file => ({
      id: Date.now().toString() + Math.random(),
      name: file.name,
      status: 'processing'
    }));

    setProcessedFiles(prev => [...prev, ...newFiles]);

    // Simulate processing and analysis
    setTimeout(() => {
      const processedFile = newFiles[0]; // Take first file for demo
      
      // Update file status
      setProcessedFiles(prev => 
        prev.map(file => 
          newFiles.find(nf => nf.id === file.id)
            ? { ...file, status: 'completed' as const, summary: 'Document analysis complete' }
            : file
        )
      );

      // Generate mock document summary
      const mockSummary = {
        id: processedFile.id,
        fileName: processedFile.name,
        summary: `Comprehensive analysis of ${processedFile.name} reveals key business insights including financial performance metrics, operational efficiency indicators, and strategic recommendations. The document contains critical information for departmental decision-making and compliance requirements.`,
        keyPoints: [
          'Revenue growth analysis with year-over-year comparisons',
          'Operational cost optimization opportunities identified',
          'Compliance requirements and regulatory adherence status', 
          'Strategic recommendations for future initiatives',
          'Risk assessment and mitigation strategies outlined'
        ],
        confidence: 0.89,
        processingTime: 3.2,
        status: 'completed' as const
      };

      // Generate AI department suggestion
      const mockAiSuggestion = {
        department: 'Finance',
        confidence: 0.87,
        reasoning: `Based on the document content analysis, this appears to be a financial document containing revenue data, budget information, and cost analysis. The presence of financial metrics and accounting terminology suggests it should be routed to the Finance department for proper handling and review.`
      };

      setSelectedDocument(mockSummary);
      setAiSuggestion(mockAiSuggestion);
      setIsProcessing(false);
      setIsAnalyzing(false);
    }, 3000);
  };

  const handleDepartmentAssign = (department: string) => {
    console.log('Document assigned to department:', department);
    // In a real implementation, this would update the document assignment in the backend
  };

  // TODO: remove mock functionality - Timeline data
  const mockTimelineItems = [
    {
      id: '1',
      title: 'Quarterly Tax Filing',
      description: 'Submit Q4 tax documents and financial statements',
      dueDate: addDays(new Date(), 7),
      status: 'due-soon' as const,
      department: 'Finance',
      priority: 'high' as const
    },
    {
      id: '2', 
      title: 'Contract Review Deadline',
      description: 'Review and approve vendor contract renewals',
      dueDate: addDays(new Date(), 14),
      status: 'upcoming' as const,
      department: 'Legal',
      priority: 'medium' as const
    },
    {
      id: '3',
      title: 'Compliance Audit',
      description: 'Annual compliance audit completion',
      dueDate: subDays(new Date(), 2),
      status: 'overdue' as const,
      department: 'Compliance',
      priority: 'high' as const
    }
  ];

  return (
    <div className="h-screen bg-background text-foreground">
      {/* Header */}
      <header className="h-16 border-b flex items-center justify-between px-6">
        <div>
          <h1 className="text-xl font-semibold" data-testid="app-title">AI Document Hub</h1>
          <p className="text-sm text-muted-foreground">Document Management & Department Assignment</p>
        </div>
        <ThemeToggle />
      </header>

      {/* Main Content - Four Panel Layout */}
      <div className="h-[calc(100vh-4rem)] flex gap-4 p-4">
        {/* Left Panel - File Upload & Processing (20%) */}
        <div className="w-1/5 space-y-4">
          <FileUploadZone 
            onFilesUpload={handleFilesUpload}
            isProcessing={isProcessing}
          />
          <ProcessedFilesList files={processedFiles} />
        </div>

        {/* Center Left Panel - Document Summary (30%) */}
        <div className="w-3/12">
          <DocumentSummary document={selectedDocument} />
        </div>

        {/* Center Right Panel - Department & Graph (30%) */}
        <div className="w-3/12 space-y-4">
          <DepartmentAssignment
            aiSuggestion={aiSuggestion}
            departments={['Finance', 'Legal', 'Human Resources', 'Operations', 'Marketing', 'IT', 'Executive', 'Compliance']}
            onAssign={handleDepartmentAssign}
            isLoading={isAnalyzing}
          />
          <div className="flex justify-center">
            <GraphVisualization />
          </div>
        </div>

        {/* Right Panel - Timeline (20%) */}
        <div className="w-1/5">
          <Timeline items={mockTimelineItems} />
        </div>
      </div>
    </div>
  );
}