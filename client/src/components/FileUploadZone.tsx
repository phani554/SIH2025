import { useState, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, FileText } from 'lucide-react';

interface FileUploadZoneProps {
  onFilesUpload: (files: File[]) => void;
  isProcessing: boolean;
}

export default function FileUploadZone({ onFilesUpload, isProcessing }: FileUploadZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      onFilesUpload(files);
    }
  }, [onFilesUpload]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      onFilesUpload(files);
    }
  }, [onFilesUpload]);

  return (
    <Card 
      className={`p-6 border-2 border-dashed transition-all duration-200 ${
        isDragOver 
          ? 'border-primary bg-primary/10' 
          : 'border-muted-foreground/25 hover:border-primary/50'
      } ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      data-testid="file-upload-zone"
    >
      <div className="flex flex-col items-center justify-center text-center space-y-4">
        <div className={`p-4 rounded-full transition-colors ${
          isDragOver ? 'bg-primary text-primary-foreground' : 'bg-muted'
        }`}>
          {isDragOver ? <FileText className="w-8 h-8" /> : <Upload className="w-8 h-8" />}
        </div>
        
        <div className="space-y-2">
          <h3 className="font-medium text-sm">
            {isDragOver ? 'Drop files here' : 'Upload Documents'}
          </h3>
          <p className="text-xs text-muted-foreground">
            Drag and drop files here or click to browse
          </p>
        </div>

        <input
          type="file"
          multiple
          onChange={handleFileInput}
          className="hidden"
          id="file-input"
          accept=".pdf,.doc,.docx,.txt,.md"
          data-testid="file-input"
        />
        
        <Button 
          variant="outline" 
          size="sm"
          onClick={() => document.getElementById('file-input')?.click()}
          disabled={isProcessing}
          data-testid="button-browse-files"
        >
          Browse Files
        </Button>
      </div>
    </Card>
  );
}