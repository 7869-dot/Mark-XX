import React, { useEffect } from 'react';
import { useStore } from './store/useStore';
import Login from './components/Login';
import Sidebar from './components/HUD/Sidebar';
import ChatWindow from './components/HUD/ChatWindow';
import InputBar from './components/HUD/InputBar';
import axios from 'axios';
import './styles/globals.css';

const App: React.FC = () => {
  const { token, user, setUser, setPersonality, setSummary, setMessages } = useStore();

  useEffect(() => {
    if (token && !user) {
      // Fetch initial data
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      
      const fetchData = async () => {
        try {
          const authConfig = { headers: { Authorization: `Bearer ${token}` } };
          
          // These endpoints would need to be handled by the backend
          // For now, we'll simulate or handle errors gracefully
          const [histRes, persRes, sumRes] = await Promise.allSettled([
            axios.get(`${backendUrl}/memory/history`, authConfig),
            axios.get(`${backendUrl}/memory/personality`, authConfig),
            axios.get(`${backendUrl}/memory/summary`, authConfig),
          ]);

          if (histRes.status === 'fulfilled') setMessages(histRes.value.data);
          if (persRes.status === 'fulfilled') setPersonality(persRes.value.data);
          if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data.summary);
          
          // Set a mock user if we don't have a specific profile endpoint yet
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
      {/* HUD Background Pattern */}
      <div className="absolute inset-0 pointer-events-none opacity-20">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,3px_100%]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_black_90%)]" />
      </div>

      <main className="flex h-full w-full relative z-10">
        <Sidebar />
        
        <section className="flex-1 flex flex-col">
          {/* Header */}
          <header className="p-4 border-b border-blue-500/10 flex justify-between items-center">
            <div className="font-mono text-[10px] text-blue-500/50 uppercase tracking-[0.3em]">
              Primary_Interface // Jarvis_OS
            </div>
            <div className="flex gap-4">
              <div className="h-1 w-24 bg-blue-500/20 rounded-full overflow-hidden">
                <div className="h-full bg-blue-400 w-2/3 animate-pulse" />
              </div>
            </div>
          </header>

          <ChatWindow />
          <InputBar />
        </section>
      </main>
    </div>
  );
};

export default App;
