import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { FileText, Clock, CheckCircle } from 'lucide-react';

interface DocumentSummaryData {
  id: string;
  fileName: string;
  summary: string;
  keyPoints: string[];
  confidence: number;
  processingTime: number;
  status: 'processing' | 'completed' | 'error';
}

interface DocumentSummaryProps {
  document?: DocumentSummaryData;
}

export default function DocumentSummary({ document }: DocumentSummaryProps) {
  if (!document) {
    return (
      <Card className="h-full">
        <CardHeader>
          <h2 className="font-semibold text-lg" data-testid="summary-title">Document Summary</h2>
          <p className="text-sm text-muted-foreground">
            Upload a document to see AI-generated analysis
          </p>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
              <FileText className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h3 className="font-medium">No Document Selected</h3>
              <p className="text-sm text-muted-foreground max-w-xs">
                Upload and process a document to see its summary and key insights here.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-lg" data-testid="summary-title">Document Summary</h2>
          <div className="flex items-center gap-2">
            {document.status === 'completed' && (
              <CheckCircle className="w-4 h-4 text-green-500" />
            )}
            {document.status === 'processing' && (
              <Clock className="w-4 h-4 text-primary animate-pulse" />
            )}
            <Badge variant="secondary" data-testid="confidence-badge">
              {Math.round(document.confidence * 100)}% confidence
            </Badge>
          </div>
        </div>
        <p className="text-sm text-muted-foreground" data-testid="document-name">
          {document.fileName}
        </p>
      </CardHeader>

      <CardContent>
        <ScrollArea className="h-80">
          <div className="space-y-6">
            {/* Main Summary */}
            <div className="space-y-3">
              <h3 className="font-medium text-base">Executive Summary</h3>
              <p className="text-sm text-muted-foreground leading-relaxed" data-testid="summary-content">
                {document.summary}
              </p>
            </div>

            {/* Key Points */}
            {document.keyPoints && document.keyPoints.length > 0 && (
              <div className="space-y-3">
                <h3 className="font-medium text-base">Key Points</h3>
                <ul className="space-y-2">
                  {document.keyPoints.map((point, index) => (
                    <li 
                      key={index}
                      className="flex items-start gap-2 text-sm"
                      data-testid={`key-point-${index}`}
                    >
                      <div className="w-1.5 h-1.5 bg-primary rounded-full mt-2 flex-shrink-0" />
                      <span className="text-muted-foreground">{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Processing Info */}
            <div className="pt-4 border-t">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Processing completed in {document.processingTime}s</span>
                <span>AI Analysis Complete</span>
              </div>
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}