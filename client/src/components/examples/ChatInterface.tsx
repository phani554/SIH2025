import { useState } from 'react';
import ChatInterface from '../ChatInterface';

export default function ChatInterfaceExample() {
  // TODO: remove mock functionality
  const [messages, setMessages] = useState([
    {
      id: '1',
      content: 'Hello! I\'ve uploaded a financial report. Can you help me understand the key metrics?',
      role: 'user' as const,
      timestamp: new Date(Date.now() - 120000)
    },
    {
      id: '2',
      content: 'I\'d be happy to help you analyze the financial report! I can see key metrics including revenue growth of 15% year-over-year, operating margin improvements, and strong cash flow performance. Would you like me to dive deeper into any specific area?',
      role: 'assistant' as const,
      timestamp: new Date(Date.now() - 60000)
    }
  ]);

  const [isLoading, setIsLoading] = useState(false);

  const handleSendMessage = (content: string) => {
    console.log('Sending message:', content);
    
    // Add user message
    const userMessage = {
      id: Date.now().toString(),
      content,
      role: 'user' as const,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage = {
        id: (Date.now() + 1).toString(),
        content: `Thanks for your question: "${content}". This is a simulated response to demonstrate the chat interface functionality.`,
        role: 'assistant' as const,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, aiMessage]);
      setIsLoading(false);
    }, 2000);
  };

  return (
    <div className="h-96 w-full max-w-2xl">
      <ChatInterface
        isEnabled={true}
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}