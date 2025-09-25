import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Calendar, Clock, AlertTriangle, CheckCircle } from 'lucide-react';
import { format, isAfter, isBefore, addDays } from 'date-fns';

interface TimelineItem {
  id: string;
  title: string;
  description: string;
  dueDate: Date;
  status: 'upcoming' | 'due-soon' | 'overdue' | 'completed';
  department?: string;
  priority: 'low' | 'medium' | 'high';
}

interface TimelineProps {
  items: TimelineItem[];
}

const getStatusColor = (status: TimelineItem['status']) => {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800';
    case 'overdue':
      return 'bg-red-100 text-red-800';
    case 'due-soon':
      return 'bg-yellow-100 text-yellow-800';
    default:
      return 'bg-blue-100 text-blue-800';
  }
};

const getStatusIcon = (status: TimelineItem['status']) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-3 h-3" />;
    case 'overdue':
      return <AlertTriangle className="w-3 h-3" />;
    case 'due-soon':
      return <Clock className="w-3 h-3" />;
    default:
      return <Calendar className="w-3 h-3" />;
  }
};

const getPriorityColor = (priority: TimelineItem['priority']) => {
  switch (priority) {
    case 'high':
      return 'border-l-red-500';
    case 'medium':
      return 'border-l-yellow-500';
    default:
      return 'border-l-blue-500';
  }
};

export default function Timeline({ items }: TimelineProps) {
  if (items.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader>
          <h3 className="font-semibold text-lg" data-testid="timeline-title">Important Deadlines</h3>
          <p className="text-sm text-muted-foreground">
            Track document processing and compliance deadlines
          </p>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
              <Calendar className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h4 className="font-medium">No Deadlines</h4>
              <p className="text-sm text-muted-foreground max-w-xs">
                Important deadlines and milestones will appear here as documents are processed.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  const sortedItems = [...items].sort((a, b) => a.dueDate.getTime() - b.dueDate.getTime());

  return (
    <Card className="h-full">
      <CardHeader>
        <h3 className="font-semibold text-lg" data-testid="timeline-title">Important Deadlines</h3>
        <p className="text-sm text-muted-foreground">
          {items.length} deadline{items.length !== 1 ? 's' : ''} tracked
        </p>
      </CardHeader>

      <CardContent>
        <ScrollArea className="h-80">
          <div className="space-y-4">
            {sortedItems.map((item, index) => (
              <div 
                key={item.id}
                className={`p-4 rounded-lg border-l-4 bg-card hover:bg-accent/50 transition-colors ${getPriorityColor(item.priority)}`}
                data-testid={`timeline-item-${item.id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-sm" data-testid={`timeline-title-${item.id}`}>
                        {item.title}
                      </h4>
                      <Badge 
                        variant="secondary" 
                        className={getStatusColor(item.status)}
                        data-testid={`timeline-status-${item.id}`}
                      >
                        {getStatusIcon(item.status)}
                        {item.status.replace('-', ' ')}
                      </Badge>
                    </div>

                    <p className="text-xs text-muted-foreground" data-testid={`timeline-description-${item.id}`}>
                      {item.description}
                    </p>

                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="w-3 h-3" />
                        <span data-testid={`timeline-date-${item.id}`}>
                          {format(item.dueDate, 'MMM dd, yyyy')}
                        </span>
                      </div>

                      {item.department && (
                        <Badge variant="outline" className="text-xs" data-testid={`timeline-department-${item.id}`}>
                          {item.department}
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}