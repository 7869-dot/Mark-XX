import React, { useState, useEffect } from 'react';
import { useStore } from '../../store/useStore';
import { useSSE } from '../../hooks/useSSE';
import { 
  User, Activity, Database, Brain, Shield, Zap, 
  Radar, Radio, Map, Crosshair, Wrench, Flame
} from 'lucide-react';
import GlassContainer from './GlassContainer';
import { motion, AnimatePresence } from 'framer-motion';

type TabType = 'intel' | 'tactical' | 'arsenal';

const Sidebar: React.FC = () => {
  const { user, personality, summary, isStreaming, logout } = useStore();
  const { startStream } = useSSE();
  const [activeTab, setActiveTab] = useState<TabType>('intel');
  const [sonarSweep, setSonarSweep] = useState(0);

  // Animate tactical sonar radar scanning sweep line
  useEffect(() => {
    const timer = setInterval(() => {
      setSonarSweep(prev => (prev + 3) % 360);
    }, 30);
    return () => clearInterval(timer);
  }, []);

  const handleQuickQuery = (query: string) => {
    if (isStreaming) return;
    startStream(query);
  };

  // Predefined Batman gadgets in Arsenal
  const arsenalItems = [
    {
      name: "THE BAT (BATWING)",
      description: "Aerial combat vehicle with heavy armor, stealth capabilities, and auto-nav.",
      query: "Give me a detailed tactical readout of 'The Bat' (Batwing) capabilities and deployment history.",
      icon: Flame,
      status: "SECURED"
    },
    {
      name: "THE BATPOD",
      description: "Escape motorcycle featuring 20mm cannons, blast shields, and grappling claws.",
      query: "Status report on the Batpod. What weapons are armed and what is the current battery charge?",
      icon: Crosshair,
      status: "ARMED"
    },
    {
      name: "EMP RIFLE",
      description: "Handheld electromagnetic pulse gun designed to silently disrupt electronics.",
      query: "How does the EMP Rifle disrupt Bane's detonator systems? Provide user instructions.",
      icon: Zap,
      status: "READY"
    },
    {
      name: "GRAPPLING GUN",
      description: "Magnetic line launcher for rapid vertical traversal and climbing maneuvers.",
      query: "What is the maximum tensile strength and range of the Batcomputer grapple gun?",
      icon: Wrench,
      status: "EQUIPPED"
    }
  ];

  // Tactical Sectors
  const sectors = [
    { name: "Gotham Sewers (Bane HQ)", status: "CRITICAL", alert: true, activity: "HIGH" },
    { name: "Downtown Bridges", status: "CLOSED", alert: true, activity: "BARRICADE" },
    { name: "Wayne Enterprises Vault", status: "COMPROMISED", alert: true, activity: "ALERT" },
    { name: "Gotham Police Dept", status: "BELEAGUERED", alert: false, activity: "STABLE" }
  ];

  return (
    <div className="w-80 h-full p-4 flex flex-col gap-4 border-r border-[#22170d]/60 bg-[#040406]/90 backdrop-blur-md relative z-20">
      {/* User profile section */}
      <GlassContainer className="p-4 bg-[#0a0808]/90 border-[#ea580c]/10">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-12 h-12 rounded-sm bg-[#ea580c]/10 flex items-center justify-center border border-[#ea580c]/30 overflow-hidden">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="User" className="w-full h-full object-cover grayscale brightness-90 contrast-125" />
              ) : (
                <User size={24} className="text-[#ea580c]" />
              )}
            </div>
            <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-red-600 border-2 border-[#040406] rounded-full animate-ping" />
            <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-[#ea580c] border-2 border-[#040406] rounded-full" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[9px] font-mono text-[#ea580c] uppercase tracking-widest glow-text flex items-center gap-1 font-bold">
              <Shield size={10} /> SECURITY_LEVEL_7
            </div>
            <div className="text-sm font-mono truncate text-[#e5e5e7] uppercase tracking-tighter font-bold">
              {user?.full_name || 'Bruce Wayne'}
            </div>
          </div>
          <button 
            onClick={logout}
            className="text-[9px] font-mono border border-red-900/40 bg-red-950/20 text-red-400 px-1.5 py-0.5 rounded-sm hover:bg-red-900/40 hover:text-white transition-all cursor-pointer"
          >
            DISCON
          </button>
        </div>
      </GlassContainer>

      {/* Interactive Tabs Header */}
      <div className="grid grid-cols-3 gap-1.5 bg-[#0e0c0c]/85 p-1 rounded-sm border border-[#22170d]/30">
        {(['intel', 'tactical', 'arsenal'] as TabType[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`py-2 text-[9px] font-mono font-bold uppercase tracking-wider rounded-sm transition-all duration-300 cursor-pointer ${
              activeTab === tab 
                ? 'bg-[#ea580c]/15 text-[#ea580c] border-b border-[#ea580c]/40' 
                : 'text-[#6b6d72] hover:text-[#e0e0e0] hover:bg-[#121010]/50'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Contents Container */}
      <div className="flex-1 flex flex-col min-h-0">
        <AnimatePresence mode="wait">
          {activeTab === 'intel' && (
            <motion.div
              key="intel"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
              className="flex-1 flex flex-col gap-4 min-h-0"
            >
              {/* Cognitive/Intelligence Traits */}
              <GlassContainer className="p-4 flex-1 flex flex-col bg-[#080708]/90 overflow-hidden">
                <div className="flex items-center justify-between mb-3 border-b border-[#22170d]/50 pb-2">
                  <div className="flex items-center gap-2 text-[#ea580c]">
                    <Brain size={14} />
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest">COGNITIVE_TRAITS</span>
                  </div>
                  <div className="w-1.5 h-1.5 rounded-full bg-[#ea580c] animate-pulse" />
                </div>
                <div className="space-y-3 font-mono text-[10px] overflow-y-auto pr-1.5 custom-scrollbar flex-1">
                  {personality?.traits ? (
                    Object.entries(personality.traits).map(([key, val]) => (
                      <div key={key} className="group border-b border-[#151212]/50 pb-1.5">
                        <div className="text-[#888888] uppercase text-[9px] mb-0.5 flex justify-between">
                          <span>{key}</span>
                          <span className="text-[#ea580c]/40">v.0.9</span>
                        </div>
                        <div className="text-[#e5e5e7] bg-[#ea580c]/5 p-2 border-l-2 border-[#ea580c]/40 group-hover:bg-[#ea580c]/10 transition-colors">
                          {String(val)}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-[#8a8d91] italic text-center py-10 animate-pulse flex flex-col items-center gap-2">
                      <Zap size={14} className="animate-spin text-[#ea580c]/40" />
                      <span>Scanning neural telemetry...</span>
                    </div>
                  )}
                </div>
              </GlassContainer>

              {/* Memory Summary */}
              <GlassContainer className="p-4 h-48 bg-[#080708]/90 flex flex-col">
                <div className="flex items-center gap-2 mb-2.5 text-[#ea580c] border-b border-[#22170d]/50 pb-2">
                  <Database size={13} />
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest">DECISION_LOG_BRIEF</span>
                </div>
                <div className="text-[10px] font-mono text-[#8a8d91] leading-relaxed overflow-y-auto h-32 pr-1 custom-scrollbar">
                  {summary ? (
                    <span className="opacity-90">{summary}</span>
                  ) : (
                    <div className="flex flex-col gap-2.5 pt-2">
                      <div className="h-2 w-full bg-[#ea580c]/10 animate-pulse rounded-full" />
                      <div className="h-2 w-4/5 bg-[#ea580c]/10 animate-pulse rounded-full" />
                      <div className="h-2 w-5/6 bg-[#ea580c]/10 animate-pulse rounded-full" />
                    </div>
                  )}
                </div>
              </GlassContainer>
            </motion.div>
          )}

          {activeTab === 'tactical' && (
            <motion.div
              key="tactical"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
              className="flex-1 flex flex-col gap-4 min-h-0"
            >
              {/* Radar Sonar & Waveform */}
              <GlassContainer className="p-4 bg-[#080708]/90 flex flex-col items-center gap-3">
                <div className="flex items-center justify-between w-full border-b border-[#22170d]/50 pb-2">
                  <div className="flex items-center gap-2 text-[#ea580c]">
                    <Radar size={14} />
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest">SONAR_GRID</span>
                  </div>
                  <span className="text-[8px] font-mono text-red-500 uppercase tracking-widest animate-pulse font-bold">SWEEP_ACTIVE</span>
                </div>

                {/* Sonar Circle Graphics */}
                <div className="relative w-36 h-36 border border-[#ea580c]/20 rounded-full flex items-center justify-center overflow-hidden bg-black/60 shadow-[inset_0_0_15px_rgba(234,88,12,0.15)]">
                  {/* Concentric rings */}
                  <div className="absolute w-28 h-28 border border-[#ea580c]/10 rounded-full" />
                  <div className="absolute w-16 h-16 border border-[#ea580c]/10 rounded-full" />
                  <div className="absolute w-6 h-6 border border-[#ea580c]/20 rounded-full bg-[#ea580c]/5" />
                  
                  {/* Radar sweep line */}
                  <div 
                    className="absolute top-1/2 left-1/2 w-18 h-0.5 bg-gradient-to-r from-transparent to-[#ea580c] origin-left z-10"
                    style={{ transform: `rotate(${sonarSweep}deg) translateY(-50%)` }}
                  />

                  {/* Pulsing Target nodes */}
                  <div className="absolute top-8 left-12 w-2 h-2 bg-red-600 rounded-full animate-ping" />
                  <div className="absolute top-8 left-12 w-2 h-2 bg-red-500 rounded-full" />
                  
                  <div className="absolute bottom-10 right-8 w-2 h-2 bg-[#ea580c] rounded-full animate-pulse" />
                  <div className="absolute bottom-10 right-8 w-2 h-2 bg-[#ea580c] rounded-full" />
                </div>

                {/* Animated Waveform for Bane Signal */}
                <div className="w-full mt-1.5">
                  <div className="flex items-center justify-between text-[8px] font-mono text-[#8a8d91] mb-1">
                    <span className="flex items-center gap-1"><Radio size={10} className="text-red-500" /> BANE_DETONATION_FREQ</span>
                    <span className="text-[#ea580c] font-bold">144.8 MHz</span>
                  </div>
                  <div className="h-8 bg-black/85 rounded-sm border border-[#22170d]/50 flex items-end justify-around p-1 overflow-hidden">
                    {Array.from({ length: 24 }).map((_, i) => (
                      <motion.div 
                        key={i}
                        className="w-1.5 bg-[#ea580c]/70 rounded-t-sm"
                        animate={{ 
                          height: [
                            `${Math.random() * 85 + 15}%`, 
                            `${Math.random() * 85 + 15}%`, 
                            `${Math.random() * 85 + 15}%`
                          ] 
                        }}
                        transition={{ 
                          repeat: Infinity, 
                          duration: Math.random() * 0.8 + 0.5,
                          ease: "easeInOut"
                        }}
                      />
                    ))}
                  </div>
                </div>
              </GlassContainer>

              {/* Tactical Sectors Grid */}
              <GlassContainer className="p-4 flex-1 overflow-y-auto custom-scrollbar bg-[#080708]/90">
                <div className="flex items-center gap-2 mb-3 text-[#ea580c] border-b border-[#22170d]/50 pb-2">
                  <Map size={13} />
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest">GOTHAM_ZONE_INTELLIGENCE</span>
                </div>
                <div className="space-y-2.5 font-mono text-[9px]">
                  {sectors.map((sec, idx) => (
                    <div 
                      key={idx} 
                      onClick={() => handleQuickQuery(`Provide tactical analysis on ${sec.name} and suggest infiltration path.`)}
                      className="p-2 border border-[#22170d]/60 bg-[#0e0c0c]/80 hover:bg-[#ea580c]/5 hover:border-[#ea580c]/40 rounded-sm flex justify-between items-center transition-all cursor-pointer duration-300"
                    >
                      <div className="flex flex-col">
                        <span className="text-[#e5e5e7] font-semibold">{sec.name}</span>
                        <span className="text-[#6b6d72] text-[8px] uppercase tracking-tighter">SIG_INT: {sec.activity}</span>
                      </div>
                      <span className={`px-1.5 py-0.5 text-[8px] font-bold rounded-sm border ${
                        sec.alert 
                          ? 'border-red-950/60 bg-red-950/35 text-red-400' 
                          : 'border-green-950/60 bg-green-950/35 text-green-400'
                      }`}>
                        {sec.status}
                      </span>
                    </div>
                  ))}
                </div>
              </GlassContainer>
            </motion.div>
          )}

          {activeTab === 'arsenal' && (
            <motion.div
              key="arsenal"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
              className="flex-1 flex flex-col gap-4 min-h-0 overflow-y-auto custom-scrollbar"
            >
              <GlassContainer className="p-4 bg-[#080708]/90 flex flex-col flex-1 min-h-0">
                <div className="flex items-center gap-2 mb-3 text-[#ea580c] border-b border-[#22170d]/50 pb-2">
                  <Crosshair size={13} />
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest">WAYNE_RD_ARSENAL</span>
                </div>
                <div className="space-y-3 overflow-y-auto pr-1 custom-scrollbar flex-1">
                  {arsenalItems.map((item, idx) => {
                    const IconComp = item.icon;
                    return (
                      <div 
                        key={idx}
                        onClick={() => handleQuickQuery(item.query)}
                        className="group p-3 border border-[#22170d]/60 bg-[#0e0c0c]/80 hover:bg-[#ea580c]/5 hover:border-[#ea580c]/40 rounded-sm transition-all duration-300 cursor-pointer"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-1.5 text-[#e5e5e7] font-semibold text-[10px] tracking-wide">
                            <IconComp size={12} className="text-[#ea580c] group-hover:animate-pulse" />
                            <span>{item.name}</span>
                          </div>
                          <span className="text-[7.5px] font-mono border border-amber-900/60 bg-amber-950/20 text-[#ea580c] px-1 py-0.5 rounded-sm">
                            {item.status}
                          </span>
                        </div>
                        <p className="text-[9px] font-mono text-[#8a8d91] leading-relaxed group-hover:text-white transition-colors">
                          {item.description}
                        </p>
                        <div className="mt-2 text-[8px] font-mono text-[#ea580c]/50 uppercase tracking-wide flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          QUERY BATCOMPUTER &gt;&gt;
                        </div>
                      </div>
                    );
                  })}
                </div>
              </GlassContainer>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Global connection/uplink status footer */}
      <GlassContainer className="p-3 bg-[#0a0808]/95 border-[#ea580c]/15">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-green-500/80">
            <Activity size={12} className="animate-pulse" />
            <span className="text-[9px] font-mono font-bold uppercase tracking-widest">UPLINK_ENCRYPT_STABLE</span>
          </div>
          <div className="text-[8px] font-mono text-[#6b6d72]">
            NODE_<span className="text-[#ea580c]">CAVE_01</span>
          </div>
        </div>
      </GlassContainer>
    </div>
  );
};

export default Sidebar;
