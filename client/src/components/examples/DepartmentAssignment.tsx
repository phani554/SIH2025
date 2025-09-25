import { useState } from 'react';
import DepartmentAssignment from '../DepartmentAssignment';

export default function DepartmentAssignmentExample() {
  // TODO: remove mock functionality
  const mockAiSuggestion = {
    department: 'Finance',
    confidence: 0.89,
    reasoning: 'This document contains financial data, revenue metrics, and budget analysis that are typically handled by the Finance department. Key indicators include quarterly reports, financial statements, and budget allocations.'
  };

  const handleAssign = (department: string) => {
    console.log('Document assigned to:', department);
  };

  return (
    <div className="h-96 w-80">
      <DepartmentAssignment 
        aiSuggestion={mockAiSuggestion}
        departments={['Finance', 'Legal', 'Human Resources', 'Operations', 'Marketing', 'IT']}
        onAssign={handleAssign}
        isLoading={false}
      />
    </div>
  );
}