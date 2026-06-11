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
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      
      const fetchData = async () => {
        try {
          const authConfig = { headers: { Authorization: `Bearer ${token}` } };
          const [histRes, persRes, sumRes, meRes] = await Promise.allSettled([
            axios.get(`${backendUrl}/memory/history`, authConfig),
            axios.get(`${backendUrl}/memory/personality`, authConfig),
            axios.get(`${backendUrl}/memory/summary`, authConfig),
            axios.get(`${backendUrl}/auth/me`, authConfig),
          ]);

          if (histRes.status === 'fulfilled') setMessages(histRes.value.data);
          if (persRes.status === 'fulfilled') setPersonality(persRes.value.data);
          if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data?.summary || '');
          if (meRes.status === 'fulfilled') {
            setUser(meRes.value.data);
          } else {
            setUser({ id: '1', email: 'bruce.wayne@waynecorp.com', full_name: 'Bruce Wayne' });
          }
        } catch (err) {
          console.error('Data fetch error:', err);
          // Fallback if endpoint fails
          setUser({ id: '1', email: 'bruce.wayne@waynecorp.com', full_name: 'Bruce Wayne' });
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
      <div className="absolute inset-0 pointer-events-none z-50 overflow-hidden">
        <div className="scanline" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_10%,_black_95%)] opacity-75" />
        <div className="industrial-grid absolute inset-0 opacity-15" />
      </div>

      <motion.main 
        initial={{ opacity: 0, scale: 1.02 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1, ease: "easeOut" }}
        className="flex h-full w-full relative z-10"
      >
        <Sidebar />
        
        <section className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <header className="p-4 border-b border-[#22170d]/50 flex justify-between items-center bg-[#080708]/75 backdrop-blur-md">
            <div className="flex flex-col">
              <div className="font-mono text-[10px] text-[#ea580c] uppercase tracking-[0.4em] glow-text font-bold">
                WAYNE-NET // TACTICAL_GRID // CA-01
              </div>
              <div className="font-mono text-[8px] text-[#888888] uppercase tracking-[0.2em] mt-0.5">
                SECURE_NODE // SHADOW_VPN_TUNNEL
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex flex-col items-end">
                <div className="text-[8.5px] font-mono text-[#ea580c]/60 uppercase tracking-wider">COGNITIVE_CORE_LOAD</div>
                <div className="h-1 w-36 bg-[#ea580c]/10 rounded-full overflow-hidden mt-1 border border-[#22170d]/40">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: ["15%", "85%", "40%", "95%", "65%"] }}
                    transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
                    className="h-full bg-gradient-to-r from-[#ea580c] to-[#f59e0b] shadow-[0_0_8px_rgba(234,88,12,0.6)]" 
                  />
                </div>
              </div>
              <div className="h-8 w-[1px] bg-[#22170d]/55" />
              <div className="text-[9.5px] font-mono text-[#ea580c] animate-pulse font-bold tracking-widest flex items-center gap-1.5 glow-text">
                <span className="w-1.5 h-1.5 rounded-full bg-[#ea580c] inline-block animate-ping" />
                BATCOMPUTER_ONLINE
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
