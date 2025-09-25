import { useState, useEffect } from 'react';
import FileUploadZone from './FileUploadZone';
import ProcessedFilesList from './ProcessedFilesList';
import DocumentSummary from './DocumentSummary';
import DepartmentAssignment from './DepartmentAssignment';
import Timeline from './Timeline';
import ThemeToggle from './ThemeToggle';
import { Task, getTasks, uploadFiles } from '../lib/api';

// This is an extended type for the frontend to handle extra properties
// that the child components might need.
type FrontendTask = Task & {
  processingTime?: number; // Kept for potential future use
};

const AVAILABLE_DEPARTMENTS = [
  'Finance',
  'Legal',
  'Human Resources',
  'Operations',
  'Marketing',
  'IT',
  'Executive',
  'Compliance',
  'Sales',
  'Research & Development'
];


export default function Dashboard() {
  const [tasks, setTasks] = useState<FrontendTask[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTask, setSelectedTask] =  useState<FrontendTask | null>(null);

  const handleSelectTask = (taskId: string) => {
    const task = tasks.find(t => t.id === taskId);
    setSelectedTask(task || null);
  };

  const fetchAndSetTasks = async () => {
    try {
      const fetchedTasks = await getTasks();
      // Sort tasks to show newest first using the timestamp
      const sortedTasks = fetchedTasks.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setTasks(sortedTasks);

      // If no task is selected or the selected one disappeared, select the first one
      if ((!selectedTask || !sortedTasks.find(t => t.id === selectedTask.id)) && sortedTasks.length > 0) {
        setSelectedTask(sortedTasks[0]);
      }

    } catch (error) {
      console.error("Dashboard: Failed to fetch tasks", error);
    }
  };

  const handleFilesUpload = async (files: File[]) => {
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      await uploadFiles(files);
      // Immediately fetch tasks after upload to show the new 'processing' file
      await fetchAndSetTasks();
    } catch (error) {
      console.error("Dashboard: File upload failed", error);
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    // Fetch initial tasks when the component loads
    fetchAndSetTasks();

    // Set up a polling mechanism to refresh tasks every 5 seconds
    const intervalId = setInterval(fetchAndSetTasks, 5000);

    // Clean up the interval when the component unmounts
    return () => clearInterval(intervalId);
  }, []); // The empty dependency array ensures this runs only once on mount

  // FIX: Simplified the data mapping. The status is now passed directly.
  // The DocumentSummary component is updated to handle the 'failed' status.
  const documentSummaryData = selectedTask ? {
    id: selectedTask.id,
    fileName: selectedTask.filename,
    summary: selectedTask.summary || 'No summary available.',
    keyPoints: selectedTask.keyPoints || [],
    status: selectedTask.status,
    confidence: selectedTask.departmentSuggestion?.confidence || 0,
    processingTime: selectedTask.processingTime || 0,
  } : undefined;

  const departmentSuggestionData = selectedTask ? selectedTask.departmentSuggestion : undefined;
  const isAnyTaskProcessing = tasks.some(task => task.status === 'processing');

  return (
    <div className="h-screen bg-background text-foreground">
      <header className="h-16 border-b flex items-center justify-between px-6">
        <div>
          <h1 className="text-xl font-semibold">AI Document Hub</h1>
          <p className="text-sm text-muted-foreground">Document Management & Department Assignment</p>
        </div>
        <ThemeToggle />
      </header>
      <div className="h-[calc(100vh-4rem)] flex gap-4 p-4">
        <div className="w-1/5 space-y-4 flex flex-col">
          <FileUploadZone onFilesUpload={handleFilesUpload} isProcessing={isUploading || isAnyTaskProcessing} />
          {/* FIX: This now works because ProcessedFilesList expects `filename`, which `FrontendTask` has. */}
          <ProcessedFilesList
            files={tasks}
            onSelectFile={handleSelectTask}
            selectedFileId={selectedTask?.id}
          />
        </div>
        <div className="w-3/12">
          <DocumentSummary document={documentSummaryData} />
        </div>
        <div className="w-3/12 space-y-4">
          {/* FIX: The 'departments' prop is now correctly passed. */}
          <DepartmentAssignment
            aiSuggestion={departmentSuggestionData}
            departments={AVAILABLE_DEPARTMENTS}
            onAssign={() => {}} // This can be implemented later
            isLoading={selectedTask?.status === 'processing'}
          />
        </div>
        <div className="w-1/5">
          <Timeline items={[]} />
        </div>
      </div>
    </div>
  );
}

