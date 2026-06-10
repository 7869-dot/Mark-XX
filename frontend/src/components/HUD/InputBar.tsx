import React, { useState } from 'react';
import { Send, Mic, Command } from 'lucide-react';
import { useSSE } from '../../hooks/useSSE';
import { useStore } from '../../store/useStore';

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
    <div className="p-6 pt-0">
      <form 
        onSubmit={handleSubmit}
        className="glass rounded-xl p-2 flex items-center gap-2 border-blue-500/20 focus-within:border-blue-500/50 transition-colors"
      >
        <div className="pl-3 text-blue-500/50">
          <Command size={18} />
        </div>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Awaiting instruction..."
          className="flex-1 bg-transparent border-none outline-none text-blue-100 font-mono text-sm py-2 placeholder:text-slate-600"
          disabled={isStreaming}
        />
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="p-2 text-slate-500 hover:text-blue-400 transition-colors"
            disabled={isStreaming}
          >
            <Mic size={18} />
          </button>
          <button
            type="submit"
            className={`p-2 rounded-lg transition-all ${
              input.trim() && !isStreaming 
                ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/40' 
                : 'text-slate-700'
            }`}
            disabled={!input.trim() || isStreaming}
          >
            <Send size={18} />
          </button>
        </div>
      </form>
      <div className="mt-2 text-[10px] text-center font-mono text-slate-600 uppercase tracking-widest">
        Secure Neural Link Active // Gemini 1.5 Pro
      </div>
    </div>
  );
};

export default InputBar;
