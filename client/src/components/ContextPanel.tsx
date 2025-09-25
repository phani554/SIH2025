import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { FileText, Search, Brain } from 'lucide-react';

interface ContextData {
  type: 'document_snippet' | 'analysis' | 'suggestion';
  title: string;
  content: string;
  source?: string;
}

interface ContextPanelProps {
  contextData?: ContextData[];
}

export default function ContextPanel({ contextData = [] }: ContextPanelProps) {
  return (
    <Card className="h-full">
      <div className="p-4 border-b">
        <h3 className="font-semibold text-lg" data-testid="context-title">Contextual Details</h3>
        <p className="text-sm text-muted-foreground">
          Document insights and analysis
        </p>
      </div>

      <ScrollArea className="flex-1 p-4" data-testid="context-content">
        {contextData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center">
              <Brain className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h4 className="font-medium">No Context Available</h4>
              <p className="text-sm text-muted-foreground max-w-xs">
                Upload documents and start chatting to see relevant context and insights appear here.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {contextData.map((item, index) => (
              <div 
                key={index}
                className="p-3 rounded-lg border bg-card"
                data-testid={`context-item-${index}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  {item.type === 'document_snippet' && <FileText className="w-4 h-4 text-primary" />}
                  {item.type === 'analysis' && <Search className="w-4 h-4 text-secondary" />}
                  {item.type === 'suggestion' && <Brain className="w-4 h-4 text-accent-foreground" />}
                  
                  <h5 className="font-medium text-sm" data-testid={`context-title-${index}`}>
                    {item.title}
                  </h5>
                </div>
                
                <p className="text-xs text-muted-foreground mb-2" data-testid={`context-content-${index}`}>
                  {item.content}
                </p>
                
                {item.source && (
                  <p className="text-xs text-primary font-medium" data-testid={`context-source-${index}`}>
                    Source: {item.source}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </ScrollArea>
    </Card>
  );
}