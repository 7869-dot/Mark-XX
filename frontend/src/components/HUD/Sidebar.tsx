import React from 'react';
import { useStore } from '../../store/useStore';
import { User, Activity, Database, Brain } from 'lucide-react';
import GlassContainer from './GlassContainer';

const Sidebar: React.FC = () => {
  const { user, personality, summary } = useStore();

  return (
    <div className="w-80 h-full p-4 flex flex-col gap-4">
      {/* User Profile */}
      <GlassContainer className="p-4" delay={0.1}>
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center border border-blue-500/30">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt="User" className="w-full h-full rounded-full" />
            ) : (
              <User size={24} className="text-blue-400" />
            )}
          </div>
          <div>
            <div className="text-sm font-bold text-blue-400 uppercase tracking-tighter">Authorized User</div>
            <div className="text-lg font-mono truncate">{user?.full_name || 'Anonymous'}</div>
          </div>
        </div>
      </GlassContainer>

      {/* Personality Layer */}
      <GlassContainer className="p-4 flex-1" delay={0.2}>
        <div className="flex items-center gap-2 mb-4 text-blue-400">
          <Brain size={18} />
          <span className="text-sm font-bold uppercase tracking-widest">User Personality</span>
        </div>
        <div className="space-y-4 font-mono text-xs overflow-y-auto max-h-[30vh]">
          {personality?.traits ? (
            Object.entries(personality.traits).map(([key, val]) => (
              <div key={key} className="border-l-2 border-blue-500/30 pl-2">
                <div className="text-blue-300 opacity-70 uppercase">{key}</div>
                <div className="text-white">{String(val)}</div>
              </div>
            ))
          ) : (
            <div className="text-slate-500 italic">Analyzing behavior...</div>
          )}
        </div>
      </GlassContainer>

      {/* Memory Summary */}
      <GlassContainer className="p-4 flex-1" delay={0.3}>
        <div className="flex items-center gap-2 mb-4 text-cyan-400">
          <Database size={18} />
          <span className="text-sm font-bold uppercase tracking-widest">Global Memory</span>
        </div>
        <div className="text-xs font-mono text-slate-300 leading-relaxed overflow-y-auto max-h-[30vh]">
          {summary || 'No conversation summary available. Jarvis is awaiting data input.'}
        </div>
      </GlassContainer>

      {/* System Status */}
      <GlassContainer className="p-4" delay={0.4}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-green-400">
            <Activity size={16} />
            <span className="text-[10px] font-bold uppercase tracking-widest">System Online</span>
          </div>
          <div className="text-[10px] font-mono text-slate-500">v0.1.0-alpha</div>
        </div>
      </GlassContainer>
    </div>
  );
};

export default Sidebar;
