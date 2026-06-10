import { useCallback, useRef } from 'react';
import { useStore } from '../store/useStore';

export const useSSE = () => {
  const { token, addMessage, updateLastMessage, setIsStreaming } = useStore();
  const eventSourceRef = useRef<EventSource | null>(null);

  const startStream = useCallback((query: string) => {
    if (!token) return;

    // 1. Add user message locally
    addMessage({ role: 'user', content: query });
    
    // 2. Add empty assistant message placeholder
    addMessage({ role: 'assistant', content: '' });
    setIsStreaming(true);

    const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
    const url = `${backendUrl}/chat/stream?query=${encodeURIComponent(query)}`;
    
    // Note: EventSource doesn't support custom headers directly. 
    // In production, we'd use a library or pass token as a query param.
    // Our backend expects the token for 'get_current_user'.
    const sseUrl = `${url}&token=${token}`; 

    const eventSource = new EventSource(sseUrl);
    eventSourceRef.current = eventSource;

    let accumulatedContent = '';

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        accumulatedContent += data.content;
        updateLastMessage(accumulatedContent);
      } catch (err) {
        console.error('SSE Parse Error:', err);
      }
    };

    eventSource.addEventListener('end', () => {
      setIsStreaming(false);
      eventSource.close();
    });

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      setIsStreaming(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [token, addMessage, updateLastMessage, setIsStreaming]);

  return { startStream };
};
