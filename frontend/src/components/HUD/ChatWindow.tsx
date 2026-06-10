import React, { useEffect, useRef } from 'react';
import { useStore } from '../../store/useStore';
import { motion, AnimatePresence } from 'framer-motion';

const ChatWindow: React.FC = () => {
  const { messages, isStreaming } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div 
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 custom-scrollbar"
    >
      <AnimatePresence>
        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
            animate={{ opacity: 1, x: 0 }}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] p-4 rounded-lg font-mono text-sm leading-relaxed ${
              msg.role === 'user' 
                ? 'bg-blue-600/20 border border-blue-500/30 text-blue-100' 
                : 'glass text-slate-200'
            }`}>
              <div className="text-[10px] uppercase tracking-widest opacity-50 mb-1">
                {msg.role === 'user' ? 'User' : 'Jarvis'}
              </div>
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.role === 'assistant' && isStreaming && idx === messages.length - 1 && (
                <motion.span
                  animate={{ opacity: [0, 1, 0] }}
                  transition={{ duration: 0.8, repeat: Infinity }}
                  className="inline-block w-2 h-4 bg-blue-400 ml-1 translate-y-1"
                />
              )}
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

export default ChatWindow;
