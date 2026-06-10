import React, { useEffect } from 'react';
import { useStore } from './store/useStore';
import Login from './components/Login';
import Sidebar from './components/HUD/Sidebar';
import ChatWindow from './components/HUD/ChatWindow';
import InputBar from './components/HUD/InputBar';
import axios from 'axios';
import { motion } from 'framer-motion';
import './styles/globals.css';

const App: React.FC = () => {
  const { token, user, setUser, setPersonality, setSummary, setMessages } = useStore();

  useEffect(() => {
    if (token && !user) {
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      
      const fetchData = async () => {
        try {
          const authConfig = { headers: { Authorization: `Bearer ${token}` } };
          const [histRes, persRes, sumRes] = await Promise.allSettled([
            axios.get(`${backendUrl}/memory/history`, authConfig),
            axios.get(`${backendUrl}/memory/personality`, authConfig),
            axios.get(`${backendUrl}/memory/summary`, authConfig),
          ]);

          if (histRes.status === 'fulfilled') setMessages(histRes.value.data);
          if (persRes.status === 'fulfilled') setPersonality(persRes.value.data);
          if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data.summary);
          
          setUser({ id: '1', email: 'user@example.com', full_name: 'Haani' });
        } catch (err) {
          console.error('Data fetch error:', err);
        }
      };

      fetchData();
    }
  }, [token, user, setUser, setPersonality, setSummary, setMessages]);

  if (!token) {
    return <Login />;
  }

  return (
    <div className="hud-container">
      {/* Cinematic HUD Overlays */}
      <div className="absolute inset-0 pointer-events-none z-50">
        <div className="scanline" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_black_95%)] opacity-60" />
        <div className="industrial-grid absolute inset-0" />
      </div>

      <motion.main 
        initial={{ opacity: 0, scale: 1.05 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.2, ease: "easeOut" }}
        className="flex h-full w-full relative z-10"
      >
        <Sidebar />
        
        <section className="flex-1 flex flex-col">
          {/* Header */}
          <header className="p-4 border-b border-[#2a2d33] flex justify-between items-center bg-[#0a0c10]/50 backdrop-blur-md">
            <div className="flex flex-col">
              <div className="font-mono text-[10px] text-[#4a9eff] uppercase tracking-[0.4em] glow-text">
                GOTH-OS // SYSTEM_SECURE
              </div>
              <div className="font-mono text-[8px] text-[#8a8d91] uppercase tracking-[0.2em]">
                NODE_01 // ENCRYPTED_LINK_ESTABLISHED
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex flex-col items-end">
                <div className="text-[9px] font-mono text-[#4a9eff]/60 uppercase">CORE_LOAD</div>
                <div className="h-1 w-32 bg-[#1e3a5f]/30 rounded-full overflow-hidden mt-1 border border-[#2a2d33]">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: "65%" }}
                    transition={{ duration: 2, repeat: Infinity, repeatType: "reverse" }}
                    className="h-full bg-[#4a9eff]/40" 
                  />
                </div>
              </div>
              <div className="h-8 w-[1px] bg-[#2a2d33]" />
              <div className="text-[10px] font-mono text-[#8a8d91] animate-pulse">
                BAT_COMPUTER_ONLINE
              </div>
            </div>
          </header>

          <ChatWindow />
          <InputBar />
        </section>
      </motion.main>
    </div>
  );
};

export default App;
