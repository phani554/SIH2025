import ContextPanel from '../ContextPanel';

export default function ContextPanelExample() {
  // TODO: remove mock functionality
  const mockContextData = [
    {
      type: 'document_snippet' as const,
      title: 'Revenue Growth Analysis',
      content: 'Q4 2024 revenue increased 15% year-over-year, driven primarily by subscription growth and enterprise customer acquisition.',
      source: 'Financial Report 2024.pdf'
    },
    {
      type: 'analysis' as const,
      title: 'Key Performance Indicators',
      content: 'Operating margin improved to 22%, customer acquisition cost decreased by 8%, and monthly recurring revenue grew 18%.',
      source: 'Financial Report 2024.pdf'
    },
    {
      type: 'suggestion' as const,
      title: 'Next Steps',
      content: 'Consider exploring the expense breakdown analysis and cash flow projections for deeper insights into financial health.'
    }
  ];

  return (
    <div className="h-96 w-80">
      <ContextPanel contextData={mockContextData} />
    </div>
  );
}