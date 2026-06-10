import React from 'react';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import { useStore } from '../store/useStore';
import { motion } from 'framer-motion';
import { Shield, Lock, Terminal } from 'lucide-react';

const Login: React.FC = () => {
  const { setToken } = useStore();

  const handleSuccess = async (credentialResponse: any) => {
    try {
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await axios.post(`${backendUrl}/auth/google`, {
        credential: credentialResponse.credential
      });
      
      const { access_token } = response.data;
      setToken(access_token);
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#050505] relative overflow-hidden">
      {/* Cinematic HUD Overlays */}
      <div className="absolute inset-0 pointer-events-none z-5">
        <div className="scanline" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_black_90%)] opacity-80" />
        <div className="industrial-grid absolute inset-0" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="glass p-12 rounded-sm flex flex-col items-center gap-10 z-10 border-[#2a2d33] bg-[#0a0c10]/90 w-[450px] relative"
      >
        {/* Corner Accents */}
        <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-[#4a9eff]/40" />
        <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-[#4a9eff]/40" />
        <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-[#4a9eff]/40" />
        <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-[#4a9eff]/40" />

        <div className="relative flex flex-col items-center">
          <div className="w-20 h-20 border border-[#2a2d33] flex items-center justify-center bg-[#1e3a5f]/10 relative">
            <Shield size={32} className="text-[#4a9eff] glow-text" />
            <motion.div 
              animate={{ opacity: [0.2, 0.5, 0.2] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="absolute inset-0 border border-[#4a9eff]/20"
            />
          </div>
          <div className="mt-6 flex flex-col items-center">
            <h1 className="text-3xl font-mono font-bold tracking-[0.2em] text-[#e0e0e0] uppercase glow-text">GOTH-OS</h1>
            <div className="flex items-center gap-2 mt-2">
              <Terminal size={12} className="text-[#4a9eff]/60" />
              <p className="text-[#8a8d91] font-mono text-[9px] uppercase tracking-[0.3em]">SECURE_TERMINAL_ACCESS</p>
            </div>
          </div>
        </div>

        <div className="w-full flex flex-col gap-6">
          <div className="border border-[#2a2d33] p-4 bg-[#050505]/50 relative">
            <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[#4a9eff]/20 to-transparent" />
            <div className="flex items-center gap-4 mb-4">
              <Lock size={14} className="text-[#4a9eff]/40" />
              <span className="text-[10px] font-mono text-[#8a8d91] uppercase tracking-widest">Identify Protocol: Google_OAuth_2.0</span>
            </div>
            <GoogleLogin
              onSuccess={handleSuccess}
              onError={() => console.log('Login Failed')}
              useOneTap
              theme="filled_black"
              shape="square"
              width="350"
            />
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <div className="text-[9px] font-mono text-[#4a9eff]/50 uppercase tracking-[0.4em] animate-pulse">
            Awaiting_Authorization...
          </div>
          <div className="w-48 h-[1px] bg-[#2a2d33]" />
          <div className="text-[8px] font-mono text-[#3a3f4a] uppercase tracking-widest">
            Level 7 Encrypted Connection // Proxy_Active
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
