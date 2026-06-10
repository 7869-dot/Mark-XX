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
      className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 custom-scrollbar relative z-10"
    >
      <AnimatePresence>
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center opacity-20 pointer-events-none">
            <div className="text-[120px] font-bold text-[#4a9eff]/10 select-none">GOTH-OS</div>
            <div className="text-xs font-mono tracking-[0.5em] text-[#4a9eff]/40">AWAITING_CRITERIA_INPUT</div>
          </div>
        )}
        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[85%] p-4 rounded-sm font-mono text-sm leading-relaxed border relative ${
              msg.role === 'user' 
                ? 'bg-[#1e3a5f]/20 border-[#4a9eff]/30 text-[#e0e0e0]' 
                : 'bg-[#0a0c10]/80 border-[#2a2d33] text-[#8a8d91]'
            }`}>
              {/* Corner Details */}
              <div className="absolute -top-px -left-px w-2 h-2 border-t border-l border-[#4a9eff]/40" />
              <div className="absolute -bottom-px -right-px w-2 h-2 border-b border-r border-[#4a9eff]/40" />

              <div className={`text-[9px] uppercase tracking-[0.2em] mb-2 font-bold ${
                msg.role === 'user' ? 'text-[#4a9eff]' : 'text-[#8a8d91]'
              }`}>
                {msg.role === 'user' ? '>> USER_UPLINK' : '>> SYSTEM_RESPONSE'}
              </div>
              
              <div className={`whitespace-pre-wrap ${msg.role === 'user' ? 'text-[#e0e0e0]' : 'text-[#8a8d91]'}`}>
                {msg.content}
              </div>

              {msg.role === 'assistant' && isStreaming && idx === messages.length - 1 && (
                <motion.span
                  animate={{ opacity: [0, 1, 0] }}
                  transition={{ duration: 0.5, repeat: Infinity }}
                  className="inline-block w-2 h-4 bg-[#4a9eff] ml-1 align-middle"
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
