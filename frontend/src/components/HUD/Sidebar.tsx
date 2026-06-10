import React from 'react';
import { useStore } from '../../store/useStore';
import { User, Activity, Database, Brain, Shield, Zap } from 'lucide-react';
import GlassContainer from './GlassContainer';

const Sidebar: React.FC = () => {
  const { user, personality, summary } = useStore();

  return (
    <div className="w-80 h-full p-4 flex flex-col gap-4 border-r border-[#2a2d33] bg-[#050505]/40 backdrop-blur-sm relative z-20">
      {/* User Profile / Auth Status */}
      <GlassContainer className="p-4 bg-[#0a0c10]/80" delay={0.1}>
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-12 h-12 rounded-sm bg-[#1e3a5f]/20 flex items-center justify-center border border-[#4a9eff]/30 overflow-hidden">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="User" className="w-full h-full object-cover" />
              ) : (
                <User size={24} className="text-[#4a9eff]" />
              )}
            </div>
            <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-500 border-2 border-[#050505] rounded-full" />
          </div>
          <div>
            <div className="text-[10px] font-mono text-[#4a9eff] uppercase tracking-wider glow-text flex items-center gap-1">
              <Shield size={10} /> Authorized_Access
            </div>
            <div className="text-md font-mono truncate text-[#e0e0e0] uppercase tracking-tighter">
              {user?.full_name || 'Anonymous_Entity'}
            </div>
          </div>
        </div>
      </GlassContainer>

      {/* Intelligence Profile */}
      <GlassContainer className="p-4 flex-1 flex flex-col bg-[#0a0c10]/80" delay={0.2}>
        <div className="flex items-center justify-between mb-4 border-b border-[#2a2d33] pb-2">
          <div className="flex items-center gap-2 text-[#4a9eff]">
            <Brain size={16} />
            <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em]">INTEL_PROFILE</span>
          </div>
          <Zap size={14} className="text-[#4a9eff] animate-pulse" />
        </div>
        <div className="space-y-4 font-mono text-[11px] overflow-y-auto pr-2 custom-scrollbar">
          {personality?.traits ? (
            Object.entries(personality.traits).map(([key, val]) => (
              <div key={key} className="group">
                <div className="text-[#8a8d91] uppercase text-[9px] mb-1 flex justify-between">
                  <span>{key}</span>
                  <span className="text-[#4a9eff]/40">v.2.4</span>
                </div>
                <div className="text-[#e0e0e0] bg-[#1e3a5f]/10 p-2 border-l border-[#4a9eff]/30 group-hover:bg-[#1e3a5f]/20 transition-colors">
                  {String(val)}
                </div>
              </div>
            ))
          ) : (
            <div className="text-[#8a8d91] italic animate-pulse">Scanning behavioral patterns...</div>
          )}
        </div>
      </GlassContainer>

      {/* Cryptic Memory Feed */}
      <GlassContainer className="p-4 h-48 bg-[#0a0c10]/80" delay={0.3}>
        <div className="flex items-center gap-2 mb-3 text-[#4a9eff]/80 border-b border-[#2a2d33] pb-2">
          <Database size={14} />
          <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em]">GLOBAL_MEMORY</span>
        </div>
        <div className="text-[10px] font-mono text-[#8a8d91] leading-relaxed overflow-y-auto h-32 custom-scrollbar">
          {summary ? (
            <span className="opacity-80">{summary}</span>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="h-2 w-full bg-[#1e3a5f]/20 animate-pulse rounded-full" />
              <div className="h-2 w-2/3 bg-[#1e3a5f]/20 animate-pulse rounded-full" />
              <div className="h-2 w-5/6 bg-[#1e3a5f]/20 animate-pulse rounded-full" />
            </div>
          )}
        </div>
      </GlassContainer>

      {/* Hardware Status */}
      <GlassContainer className="p-3 bg-[#0a0c10]/90 border-[#4a9eff]/20" delay={0.4}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-green-500/80">
            <Activity size={14} />
            <span className="text-[9px] font-mono font-bold uppercase tracking-widest">UPLINK_STABLE</span>
          </div>
          <div className="text-[9px] font-mono text-[#8a8d91]">
            <span className="text-[#4a9eff]/50">REV_</span>0.1.0-DARK
          </div>
        </div>
      </GlassContainer>
    </div>
  );
};

export default Sidebar;
