import { useState, useEffect, useRef } from 'react';
import FileUploadZone from './FileUploadZone';
import ProcessedFilesList from './ProcessedFilesList';
import DocumentSummary from './DocumentSummary';
import DepartmentAssignment from './DepartmentAssignment';
import Timeline from './Timeline';
import ThemeToggle from './ThemeToggle';
import { Task, getTasks, uploadFiles } from '../lib/api';

type FrontendTask = Task & {
  processingTime?: number;
};

const AVAILABLE_DEPARTMENTS = [
  'Finance', 'Legal', 'Human Resources', 'Operations', 'Marketing', 'IT', 
  'Executive', 'Compliance', 'Sales', 'Research & Development'
];

export default function Dashboard() {
  const [tasks, setTasks] = useState<FrontendTask[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<FrontendTask | null>(null);
  
  const pollingIntervalRef = useRef<number | null>(null);

  const handleSelectTask = (taskId: string) => {
    const task = tasks.find((t: Task) => t.id === taskId);
    setSelectedTask(task || null);
  };

  const fetchAndSetTasks = async () => {
    try {
      const fetchedTasks = await getTasks();
      const sortedTasks = fetchedTasks.sort((a: Task, b: Task) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
      setTasks(sortedTasks);

      if ((!selectedTask || !sortedTasks.find((t: Task) => t.id === selectedTask.id)) && sortedTasks.length > 0) {
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
      await fetchAndSetTasks();
    } catch (error) {
      console.error("Dashboard: File upload failed", error);
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    fetchAndSetTasks();
  }, []);

  useEffect(() => {
    const isAnyTaskProcessing = tasks.some(task => task.status === 'processing');

    if (isAnyTaskProcessing) {
      if (pollingIntervalRef.current === null) {
        console.log("Starting polling: A task is processing.");
        pollingIntervalRef.current = window.setInterval(fetchAndSetTasks, 5000);
      }
    } else {
      if (pollingIntervalRef.current !== null) {
        console.log("Stopping polling: All tasks are complete.");
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    return () => {
      if (pollingIntervalRef.current !== null) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [tasks]);

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
          <ProcessedFilesList
            files={tasks.map(task => ({ id: task.id, name: task.filename, filename: task.filename, status: task.status }))}
            onSelectFile={handleSelectTask}
            selectedFileId={selectedTask?.id}
          />
        </div>
        <div className="w-3/12">
          <DocumentSummary document={documentSummaryData} />
        </div>
        <div className="w-3/12 space-y-4">
          <DepartmentAssignment
            aiSuggestion={departmentSuggestionData}
            departments={AVAILABLE_DEPARTMENTS}
            onAssign={() => {}} 
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

