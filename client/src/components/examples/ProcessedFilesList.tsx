import ProcessedFilesList from '../ProcessedFilesList';

export default function ProcessedFilesListExample() {
  // TODO: remove mock functionality
  const mockFiles = [
    { id: '1', name: 'Financial Report 2024.pdf', status: 'completed' as const, summary: 'Q4 revenue analysis' },
    { id: '2', name: 'Project Proposal.docx', status: 'processing' as const },
    { id: '3', name: 'Meeting Notes.txt', status: 'completed' as const, summary: 'Weekly team sync notes' },
  ];

  return (
    <div className="w-64">
      <ProcessedFilesList files={mockFiles} />
    </div>
  );
}