import React, { useState } from 'react';
import { Send, Mic, Terminal, Zap, Shield } from 'lucide-react';
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
    <div className="p-6 pt-0 relative z-20 bg-[#050507]">
      <form 
        onSubmit={handleSubmit}
        className="glass rounded-sm p-1.5 flex items-center gap-2 border-[#22170d]/50 focus-within:border-[#ea580c]/60 focus-within:shadow-[0_0_15px_rgba(234,88,12,0.15)] transition-all bg-[#0a0808]/90"
      >
        <div className="pl-3 text-[#ea580c]/40 focus-within:text-[#ea580c]">
          <Terminal size={15} />
        </div>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="ENTER_TACTICAL_COMMAND..."
          className="flex-1 bg-transparent border-none outline-none text-[#e5e5e7] font-mono text-[13px] py-2 placeholder:text-[#4a4747] tracking-wider focus:ring-0 focus:outline-none"
          disabled={isStreaming}
        />
        <div className="flex items-center gap-2 pr-2">
          {isStreaming && (
            <motion.div 
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              className="flex items-center gap-1.5 text-[#ea580c] text-[9.5px] font-mono uppercase tracking-widest pr-2 font-bold"
            >
              <Zap size={10} className="animate-bounce" /> Uplink Transmitting...
            </motion.div>
          )}
          <button
            type="button"
            title="Audio Input Protocol"
            className="p-2 text-[#8a8d91] hover:text-[#ea580c] transition-colors cursor-pointer"
            disabled={isStreaming}
          >
            <Mic size={16} />
          </button>
          <button
            type="submit"
            title="Execute Command"
            className={`p-2.5 rounded-sm transition-all border cursor-pointer ${
              input.trim() && !isStreaming 
                ? 'bg-[#ea580c]/15 border-[#ea580c]/35 text-[#ea580c] hover:bg-[#ea580c]/30 hover:text-white' 
                : 'border-transparent text-[#221c17]'
            }`}
            disabled={!input.trim() || isStreaming}
          >
            <Send size={15} />
          </button>
        </div>
      </form>
      <div className="mt-3 flex justify-between items-center px-1">
        <div className="text-[8.5px] font-mono text-[#ea580c]/45 uppercase tracking-[0.3em] flex items-center gap-1">
          <Shield size={10} /> BAT-NET_LINK: SECURE_CAVE_SERVER_v9.42
        </div>
        <div className="text-[8.5px] font-mono text-[#6b6d72] uppercase tracking-[0.15em]">
          CIPHER: AES_MIL_256_GCM
        </div>
      </div>
    </div>
  );
};

export default InputBar;
