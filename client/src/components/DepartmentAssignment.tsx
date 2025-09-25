import { useState } from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Brain, Building2, CheckCircle, AlertCircle } from 'lucide-react';

interface DepartmentSuggestion {
  department: string;
  confidence: number;
  reasoning: string;
}

interface DepartmentAssignmentProps {
  aiSuggestion?: DepartmentSuggestion;
  departments: string[];
  onAssign: (department: string) => void;
  isLoading?: boolean;
}

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

export default function DepartmentAssignment({ 
  aiSuggestion, 
  departments = AVAILABLE_DEPARTMENTS,
  onAssign,
  isLoading = false 
}: DepartmentAssignmentProps) {
  const [selectedDepartment, setSelectedDepartment] = useState<string>(
    aiSuggestion?.department || ''
  );
  const [isAssigned, setIsAssigned] = useState(false);

  const handleAssign = () => {
    if (selectedDepartment) {
      onAssign(selectedDepartment);
      setIsAssigned(true);
    }
  };

  const handleOverride = () => {
    setIsAssigned(false);
  };

  if (!aiSuggestion && !isLoading) {
    return (
      <Card className="h-full">
        <CardHeader>
          <h3 className="font-semibold text-lg" data-testid="assignment-title">Department Assignment</h3>
          <p className="text-sm text-muted-foreground">
            Process a document to see AI department recommendations
          </p>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-full">
          <div className="text-center space-y-4">
            <div className="w-16 h-16 mx-auto bg-muted rounded-full flex items-center justify-center">
              <Building2 className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <h4 className="font-medium">Awaiting Document Analysis</h4>
              <p className="text-sm text-muted-foreground max-w-xs">
                Upload a document to receive AI-powered department assignment suggestions.
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
          <h3 className="font-semibold text-lg" data-testid="assignment-title">Department Assignment</h3>
          {isAssigned && (
            <Badge variant="default" className="bg-green-100 text-green-800" data-testid="assignment-status">
              <CheckCircle className="w-3 h-3 mr-1" />
              Assigned
            </Badge>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          Review and confirm the AI recommendation
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="text-center space-y-3">
              <Brain className="w-8 h-8 mx-auto text-primary animate-pulse" />
              <p className="text-sm text-muted-foreground">Analyzing document for department assignment...</p>
            </div>
          </div>
        ) : (
          <>
            {/* AI Suggestion */}
            {aiSuggestion && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-primary" />
                  <h4 className="font-medium text-sm">AI Recommendation</h4>
                  <Badge variant="secondary" data-testid="ai-confidence">
                    {Math.round(aiSuggestion.confidence * 100)}% confidence
                  </Badge>
                </div>
                
                <div className="p-4 bg-primary/5 rounded-lg border">
                  <div className="flex items-center gap-2 mb-2">
                    <Building2 className="w-4 h-4 text-primary" />
                    <span className="font-medium" data-testid="suggested-department">
                      {aiSuggestion.department}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground" data-testid="suggestion-reasoning">
                    {aiSuggestion.reasoning}
                  </p>
                </div>
              </div>
            )}

            {/* Manager Override */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-secondary" />
                <h4 className="font-medium text-sm">Manager Verification</h4>
              </div>

              <div className="space-y-3">
                <Select 
                  value={selectedDepartment} 
                  onValueChange={setSelectedDepartment}
                  disabled={isAssigned}
                >
                  <SelectTrigger data-testid="department-select">
                    <SelectValue placeholder="Select department" />
                  </SelectTrigger>
                  <SelectContent>
                    {departments.map((dept) => (
                      <SelectItem key={dept} value={dept} data-testid={`department-option-${dept}`}>
                        {dept}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <div className="flex gap-2">
                  {!isAssigned ? (
                    <Button 
                      onClick={handleAssign}
                      disabled={!selectedDepartment}
                      className="flex-1"
                      data-testid="button-assign"
                    >
                      Assign Document
                    </Button>
                  ) : (
                    <Button 
                      onClick={handleOverride}
                      variant="outline"
                      className="flex-1"
                      data-testid="button-reassign"
                    >
                      Reassign
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}