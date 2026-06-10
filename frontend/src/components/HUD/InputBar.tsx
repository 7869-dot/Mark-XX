import React, { useState } from 'react';
import { Send, Mic, Terminal, Zap } from 'lucide-react';
import { useSSE } from '../../hooks/useSSE';
import { useStore } from '../../store/useStore';
import { motion } from 'framer-motion';

const InputBar: React.FC = () => {
  const [input, setInput] = useState('');
  const { startStream } = useSSE();
  const { isStreaming } = useStore();

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isStreaming) return;
    
    startStream(input);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-6 pt-0 relative z-20">
      <form 
        onSubmit={handleSubmit}
        className="glass rounded-sm p-1.5 flex items-center gap-2 border-[#2a2d33] focus-within:border-[#4a9eff]/50 transition-all bg-[#0a0c10]/90"
      >
        <div className="pl-3 text-[#4a9eff]/40">
          <Terminal size={16} />
        </div>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="ENTER_INSTRUCTION..."
          className="flex-1 bg-transparent border-none outline-none text-[#e0e0e0] font-mono text-sm py-2 placeholder:text-[#3a3f4a] tracking-wider"
          disabled={isStreaming}
        />
        <div className="flex items-center gap-2 pr-2">
          {isStreaming && (
            <motion.div 
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="flex items-center gap-1 text-[#4a9eff] text-[10px] font-mono uppercase tracking-tighter pr-2"
            >
              <Zap size={10} /> Transmitting...
            </motion.div>
          )}
          <button
            type="button"
            className="p-2 text-[#8a8d91] hover:text-[#4a9eff] transition-colors"
            disabled={isStreaming}
          >
            <Mic size={18} />
          </button>
          <button
            type="submit"
            className={`p-2 rounded-sm transition-all border ${
              input.trim() && !isStreaming 
                ? 'bg-[#1e3a5f]/30 border-[#4a9eff]/30 text-[#4a9eff] hover:bg-[#1e3a5f]/50' 
                : 'border-transparent text-[#2a2d33]'
            }`}
            disabled={!input.trim() || isStreaming}
          >
            <Send size={18} />
          </button>
        </div>
      </form>
      <div className="mt-3 flex justify-between items-center px-1">
        <div className="text-[9px] font-mono text-[#4a9eff]/40 uppercase tracking-[0.3em]">
          UPLINK_STATUS: OPTIMAL
        </div>
        <div className="text-[9px] font-mono text-[#8a8d91] uppercase tracking-[0.1em]">
          SECURE_ENCRYPTION_LAYER_v4.2.0
        </div>
      </div>
    </div>
  );
};

export default InputBar;
