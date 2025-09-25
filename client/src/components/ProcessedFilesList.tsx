import { Card, CardContent } from '@/components/ui/card';
import { FileText, Clock, CheckCircle, XCircle } from 'lucide-react';

// FIX: Changed 'name' to 'filename' to match the Task type from the API.
// This resolves the primary type mismatch error from Dashboard.tsx.
export type ProcessedFile = {
  id: string;
  filename: string; 
  status: 'processing' | 'completed' | 'failed';
};

interface ProcessedFilesListProps {
  files: ProcessedFile[];
  onSelectFile: (fileId: string) => void;
  selectedFileId?: string | null;
}

const StatusIcon = ({ status }: { status: ProcessedFile['status'] }) => {
  switch (status) {
    case 'processing':
      return <Clock className="w-4 h-4 text-yellow-500" />;
    case 'completed':
      return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
    default:
      return null;
  }
};

export default function ProcessedFilesList({ files, onSelectFile, selectedFileId }: ProcessedFilesListProps) {
  if (files.length === 0) {
    return (
      <Card className="flex-1 flex items-center justify-center bg-muted/25 border-dashed">
        <div className="text-center p-4">
          <FileText className="mx-auto w-8 h-8 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">No documents processed yet</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="flex-1 flex flex-col">
      <CardContent className="p-4 space-y-2 overflow-y-auto">
        {files.map((file) => (
          <div
            key={file.id}
            onClick={() => onSelectFile(file.id)}
            className={`flex items-center space-x-3 p-2 rounded-md cursor-pointer transition-colors ${
              selectedFileId === file.id
                ? 'bg-primary/20'
                : 'hover:bg-muted/50'
            }`}
          >
            <StatusIcon status={file.status} />
            {/* FIX: Using 'filename' to display the name of the file. */}
            <span className="text-sm truncate flex-1">{file.filename}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
