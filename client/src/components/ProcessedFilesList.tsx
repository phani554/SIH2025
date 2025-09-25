import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import { CheckCircle, FileText, Clock } from 'lucide-react';

export interface ProcessedFile {
  id: string;
  name: string;
  status: 'processing' | 'completed' | 'error';
  summary?: string;
}

interface ProcessedFilesListProps {
  files: ProcessedFile[];
}

export default function ProcessedFilesList({ files }: ProcessedFilesListProps) {
  if (files.length === 0) {
    return (
      <Card className="p-4">
        <div className="text-center text-muted-foreground text-sm">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No documents processed yet</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-4">
      <h3 className="font-medium text-sm mb-3" data-testid="processed-files-title">
        Processed Documents
      </h3>
      <ScrollArea className="h-64">
        <div className="space-y-2">
          {files.map((file) => (
            <div 
              key={file.id}
              className="flex items-center space-x-3 p-2 rounded-md hover:bg-accent/50 transition-colors"
              data-testid={`file-item-${file.id}`}
            >
              <div className="flex-shrink-0">
                {file.status === 'completed' && (
                  <CheckCircle className="w-4 h-4 text-green-500" data-testid={`status-completed-${file.id}`} />
                )}
                {file.status === 'processing' && (
                  <Clock className="w-4 h-4 text-primary animate-pulse" data-testid={`status-processing-${file.id}`} />
                )}
                {file.status === 'error' && (
                  <div className="w-4 h-4 rounded-full bg-destructive" data-testid={`status-error-${file.id}`} />
                )}
              </div>
              
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate" data-testid={`file-name-${file.id}`}>
                  {file.name}
                </p>
                {file.summary && (
                  <p className="text-xs text-muted-foreground truncate" data-testid={`file-summary-${file.id}`}>
                    {file.summary}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </Card>
  );
}