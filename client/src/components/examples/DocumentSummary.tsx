import DocumentSummary from '../DocumentSummary';

export default function DocumentSummaryExample() {
  // TODO: remove mock functionality
  const mockDocument = {
    id: '1',
    fileName: 'Q4_Financial_Report_2024.pdf',
    summary: 'This comprehensive financial report covers Q4 2024 performance with revenue growth of 15% year-over-year, reaching $2.4 million. The company demonstrated strong operational efficiency with improved margins and successful cost management initiatives. Key highlights include expansion into new markets, increased customer retention rates, and strategic investments in technology infrastructure.',
    keyPoints: [
      'Revenue increased 15% YoY to $2.4M in Q4 2024',
      'Operating margin improved from 18% to 22%',
      'Customer acquisition cost decreased by 12%',
      'Monthly recurring revenue grew 18%',
      'Successfully expanded into 3 new geographic markets',
      'Technology infrastructure investments totaled $150K'
    ],
    confidence: 0.92,
    processingTime: 3.2,
    status: 'completed' as const
  };

  return (
    <div className="h-96 w-full max-w-2xl">
      <DocumentSummary document={mockDocument} />
    </div>
  );
}