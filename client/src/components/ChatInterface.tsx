import { useState, useRef, useEffect } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Send } from 'lucide-react';
import MessageBubble, { type Message } from './MessageBubble';
import TypingIndicator from './TypingIndicator';

interface ChatInterfaceProps {
  isEnabled: boolean;
  messages: Message[];
  onSendMessage: (content: string) => void;
  isLoading: boolean;
}

export default function ChatInterface({ 
  isEnabled, 
  messages, 
  onSendMessage, 
  isLoading 
}: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('');
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading && isEnabled) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <Card className="h-full flex flex-col">
      {/* Chat Header */}
      <div className="p-4 border-b">
        <h2 className="font-semibold text-lg" data-testid="chat-title">AI Assistant</h2>
        <p className="text-sm text-muted-foreground">
          {isEnabled 
            ? 'Ask questions about your uploaded documents' 
            : 'Upload a document to start chatting'
          }
        </p>
      </div>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4" ref={scrollAreaRef} data-testid="chat-messages">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-center">
            <div className="max-w-md space-y-3">
              <div className="w-16 h-16 mx-auto bg-primary/10 rounded-full flex items-center justify-center">
                <Send className="w-8 h-8 text-primary" />
              </div>
              <h3 className="font-medium">Welcome to AI Document Hub</h3>
              <p className="text-sm text-muted-foreground">
                Upload documents to get started with intelligent analysis and chat assistance.
              </p>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isLoading && <TypingIndicator />}
      </ScrollArea>

      {/* Message Input */}
      <div className="p-4 border-t">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={isEnabled ? "Ask about your documents..." : "Upload a document first"}
            disabled={!isEnabled || isLoading}
            className="flex-1"
            data-testid="chat-input"
          />
          <Button 
            type="submit" 
            size="icon"
            disabled={!isEnabled || !inputValue.trim() || isLoading}
            data-testid="button-send-message"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
      </div>
    </Card>
  );
}