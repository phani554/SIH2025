import Timeline from '../Timeline';
import { addDays, subDays } from 'date-fns';

export default function TimelineExample() {
  // TODO: remove mock functionality
  const mockTimelineItems = [
    {
      id: '1',
      title: 'Quarterly Tax Filing',
      description: 'Submit Q4 tax documents and financial statements to regulatory authorities',
      dueDate: addDays(new Date(), 7),
      status: 'due-soon' as const,
      department: 'Finance',
      priority: 'high' as const
    },
    {
      id: '2',
      title: 'Employee Performance Reviews',
      description: 'Complete annual performance evaluations for all team members',
      dueDate: addDays(new Date(), 14),
      status: 'upcoming' as const,
      department: 'Human Resources',
      priority: 'medium' as const
    },
    {
      id: '3',
      title: 'Contract Renewal Deadline',
      description: 'Renew vendor contracts for IT services and software licenses',
      dueDate: subDays(new Date(), 2),
      status: 'overdue' as const,
      department: 'Legal',
      priority: 'high' as const
    },
    {
      id: '4',
      title: 'Compliance Audit Report',
      description: 'Submit annual compliance audit findings and remediation plan',
      dueDate: subDays(new Date(), 5),
      status: 'completed' as const,
      department: 'Compliance',
      priority: 'high' as const
    },
    {
      id: '5',
      title: 'Budget Planning Session',
      description: 'Finalize next fiscal year budget allocations and departmental requests',
      dueDate: addDays(new Date(), 21),
      status: 'upcoming' as const,
      department: 'Finance',
      priority: 'medium' as const
    }
  ];

  return (
    <div className="h-96 w-80">
      <Timeline items={mockTimelineItems} />
    </div>
  );
}