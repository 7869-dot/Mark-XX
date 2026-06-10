import React, { useEffect, useRef } from 'react';
import { useStore } from '../../store/useStore';
import { motion, AnimatePresence } from 'framer-motion';
import { Cpu, ShieldCheck } from 'lucide-react';

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
      className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 custom-scrollbar relative z-10 bg-[#050507]"
    >
      <AnimatePresence>
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center opacity-20 pointer-events-none select-none">
            {/* Massive Nolan Bat Symbol Silhouette in center of chat window */}
            <motion.div
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 0.1, scale: 1 }}
              transition={{ duration: 2, repeat: Infinity, repeatType: "reverse" }}
              className="w-80 h-44 mb-4 filter drop-shadow-[0_0_15px_rgba(234,88,12,0.25)]"
            >
              <svg viewBox="0 0 200 140" className="w-full h-full fill-neutral-900 stroke-[#ea580c] stroke-1">
                <path d="M 100,20 C 102,20 104,22 106,25 C 109,29 111,32 113,32 C 115,32 116,29 119,25 C 121,22 123,20 125,20 C 127,20 128,21 129,23 C 132,27 135,32 138,36 C 145,46 153,53 162,58 C 172,63 182,65 192,65 C 196,65 200,64 200,64 C 200,64 195,68 188,73 C 180,78 171,85 163,94 C 158,100 154,106 150,113 C 148,116 146,120 145,120 C 144,120 142,118 139,114 C 134,107 127,101 120,96 C 114,92 107,89 100,88 C 93,89 86,92 80,96 C 73,101 66,107 61,114 C 58,118 56,120 55,120 C 54,120 52,116 50,113 C 46,106 42,100 37,94 C 29,85 20,78 12,73 C 5,68 0,64 0,64 C 0,64 4,65 8,65 C 18,65 28,63 38,58 C 47,53 55,46 62,36 C 65,32 68,27 71,23 C 72,21 73,20 75,20 C 77,20 79,22 81,25 C 84,29 85,32 87,32 C 89,32 91,29 94,25 C 96,22 98,20 100,20 Z" />
              </svg>
            </motion.div>
            <div className="text-sm font-mono tracking-[0.6em] text-[#ea580c] glow-text uppercase font-bold">BATCOMPUTER_STANDBY</div>
            <div className="text-[9px] font-mono tracking-[0.2em] text-[#6b6d72] mt-1 uppercase">SECURE_VPN_TUNNEL_ESTABLISHED // PORT_5173</div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] p-4 rounded-sm font-mono text-[12.5px] leading-relaxed border relative shadow-lg ${
              msg.role === 'user' 
                ? 'bg-[#ea580c]/5 border-[#ea580c]/30 text-[#f3f4f6]' 
                : 'bg-[#0f0d0e]/95 border-[#28211a]/80 text-[#d4d4d6]'
            }`}>
              {/* Sharp Tactical Edge Accents */}
              <div className={`absolute -top-px -left-px w-2.5 h-2.5 border-t border-l ${
                msg.role === 'user' ? 'border-[#ea580c]/60' : 'border-[#6b6d72]/50'
              }`} />
              <div className={`absolute -bottom-px -right-px w-2.5 h-2.5 border-b border-r ${
                msg.role === 'user' ? 'border-[#ea580c]/60' : 'border-[#6b6d72]/50'
              }`} />

              {/* Message Header/Metadata */}
              <div className="flex items-center gap-2 mb-2">
                {msg.role === 'user' ? (
                  <>
                    <ShieldCheck size={11} className="text-[#ea580c]" />
                    <span className="text-[9px] uppercase tracking-[0.25em] font-bold text-[#ea580c] glow-text">
                      &gt;&gt; SECURE_UPLINK_COMMAND
                    </span>
                  </>
                ) : (
                  <>
                    <Cpu size={11} className="text-red-500 animate-pulse" />
                    <span className="text-[9px] uppercase tracking-[0.25em] font-bold text-red-500">
                      &gt;&gt; BATCOMPUTER_MAINFRAME
                    </span>
                  </>
                )}
                <span className="text-[7.5px] text-[#6b6d72] uppercase ml-auto">
                  {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
              
              {/* Message Body Content */}
              <div className="whitespace-pre-wrap font-mono select-text selection:bg-[#ea580c]/35 selection:text-white">
                {msg.content}
                
                {msg.role === 'assistant' && isStreaming && idx === messages.length - 1 && (
                  <motion.span
                    animate={{ opacity: [0, 1, 0] }}
                    transition={{ duration: 0.5, repeat: Infinity }}
                    className="inline-block w-1.5 h-4 bg-[#ea580c] ml-1.5 align-middle shadow-[0_0_8px_rgba(234,88,12,0.8)]"
                  />
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};

export default ChatWindow;
