import MessageBubble from '../MessageBubble';

export default function MessageBubbleExample() {
  // TODO: remove mock functionality
  const userMessage = {
    id: '1',
    content: 'Can you help me analyze the financial data in the uploaded report?',
    role: 'user' as const,
    timestamp: new Date()
  };

  const assistantMessage = {
    id: '2',
    content: 'I\'d be happy to help you analyze the financial data! I can see you\'ve uploaded a financial report. Let me review the key metrics and provide insights on revenue trends, expense analysis, and performance indicators.',
    role: 'assistant' as const,
    timestamp: new Date()
  };

  return (
    <div className="w-full max-w-2xl space-y-4 p-4">
      <MessageBubble message={userMessage} />
      <MessageBubble message={assistantMessage} />
    </div>
  );
}