import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import { useStore } from '../store/useStore';
import { motion } from 'framer-motion';
import { Lock, Terminal, Key, Loader, Zap } from 'lucide-react';

const Login: React.FC = () => {
  const { setToken } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSuccess = async (credentialResponse: any) => {
    try {
      setLoading(true);
      setError(null);
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await axios.post(`${backendUrl}/auth/google`, {
        credential: credentialResponse.credential
      });
      
      const { access_token } = response.data;
      setToken(access_token);
    } catch (err: any) {
      console.error('Login failed:', err);
      setError(err?.response?.data?.detail || 'Authentication failed. Ensure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleGuestLogin = async () => {
    try {
      setLoading(true);
      setError(null);
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await axios.post(`${backendUrl}/auth/guest`);
      
      const { access_token } = response.data;
      setToken(access_token);
    } catch (err: any) {
      console.error('Guest login failed:', err);
      setError('Guest authentication failed. Make sure the backend is active.');
    } finally {
      setLoading(false);
    }
  };

  // Generate floating ember metadata
  const embers = Array.from({ length: 30 }, (_, i) => ({
    id: i,
    size: Math.random() * 3.5 + 1,
    left: Math.random() * 100,
    delay: Math.random() * 4,
    duration: Math.random() * 5 + 4,
  }));

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-[#030303] relative overflow-hidden font-sans">
      {/* Background Embers Particle System */}
      <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="scanline" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_10%,_black_90%)] opacity-80" />
        <div className="industrial-grid absolute inset-0 opacity-15" />
        
        {/* Cinematic Floating Fire Embers */}
        {embers.map((emb) => (
          <motion.div
            key={emb.id}
            className="absolute rounded-full opacity-60"
            style={{
              width: emb.size,
              height: emb.size,
              left: `${emb.left}%`,
              bottom: '-10px',
              background: 'radial-gradient(circle, #f97316 0%, #ea580c 50%, #b45309 100%)',
              filter: 'blur(0.5px)',
            }}
            animate={{
              y: ['0vh', '-105vh'],
              x: ['0px', `${(Math.random() - 0.5) * 80}px`],
              opacity: [0.1, 0.8, 0],
              scale: [1, 1.3, 0.5],
            }}
            transition={{
              duration: emb.duration,
              delay: emb.delay,
              repeat: Infinity,
              ease: 'easeOut',
            }}
          />
        ))}
      </div>

      {/* Main Container */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1, ease: 'easeOut' }}
        className="glass p-10 rounded-sm flex flex-col items-center gap-8 z-10 border-[#332211]/40 bg-[#07070a]/95 w-[460px] relative shadow-[0_0_50px_rgba(0,0,0,0.9)]"
      >
        {/* Ember/Fire Glow Accent Lines */}
        <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#ea580c]/50" />
        <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#ea580c]/50" />
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#ea580c]/50" />
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#ea580c]/50" />

        {/* Nolan Bat Symbol Header */}
        <div className="relative flex flex-col items-center w-full">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1.2, delay: 0.2 }}
            className="w-44 h-20 flex items-center justify-center filter drop-shadow-[0_0_12px_rgba(234,88,12,0.4)] hover:drop-shadow-[0_0_20px_rgba(234,88,12,0.6)] cursor-pointer transition-all duration-500"
          >
            <svg viewBox="0 0 200 140" className="w-full h-full fill-neutral-900 stroke-[#ea580c]/40 stroke-[1.5px] hover:stroke-[#ea580c]/70 hover:fill-neutral-950 transition-all duration-500">
              <path d="M 100,20 C 102,20 104,22 106,25 C 109,29 111,32 113,32 C 115,32 116,29 119,25 C 121,22 123,20 125,20 C 127,20 128,21 129,23 C 132,27 135,32 138,36 C 145,46 153,53 162,58 C 172,63 182,65 192,65 C 196,65 200,64 200,64 C 200,64 195,68 188,73 C 180,78 171,85 163,94 C 158,100 154,106 150,113 C 148,116 146,120 145,120 C 144,120 142,118 139,114 C 134,107 127,101 120,96 C 114,92 107,89 100,88 C 93,89 86,92 80,96 C 73,101 66,107 61,114 C 58,118 56,120 55,120 C 54,120 52,116 50,113 C 46,106 42,100 37,94 C 29,85 20,78 12,73 C 5,68 0,64 0,64 C 0,64 4,65 8,65 C 18,65 28,63 38,58 C 47,53 55,46 62,36 C 65,32 68,27 71,23 C 72,21 73,20 75,20 C 77,20 79,22 81,25 C 84,29 85,32 87,32 C 89,32 91,29 94,25 C 96,22 98,20 100,20 Z" />
            </svg>
          </motion.div>
          <div className="mt-4 flex flex-col items-center">
            <h1 className="text-2xl font-mono font-bold tracking-[0.25em] text-[#f5f5f5] uppercase drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">WAYNE-NET</h1>
            <div className="flex items-center gap-1.5 mt-1.5">
              <Terminal size={11} className="text-[#ea580c]/60 animate-pulse" />
              <p className="text-[#888888] font-mono text-[9px] uppercase tracking-[0.3em]">SECURE_TACTICAL_PORTAL</p>
            </div>
          </div>
        </div>

        {/* Auth Interface */}
        <div className="w-full flex flex-col gap-5">
          <div className="border border-[#2a2d33] p-5 bg-[#050507]/90 relative rounded-sm">
            <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-[#ea580c]/25 to-transparent" />
            
            <div className="flex items-center gap-2 mb-4">
              <Lock size={12} className="text-[#ea580c]/50" />
              <span className="text-[9px] font-mono text-[#8a8d91] uppercase tracking-widest">Protocol: OAuth_Credential</span>
            </div>
            
            <div className="flex justify-center w-full">
              <GoogleLogin
                onSuccess={handleSuccess}
                onError={() => setError('Google Sign-In failed. Please try again.')}
                useOneTap
                theme="filled_black"
                shape="square"
                width="360"
              />
            </div>
          </div>

          {/* Guest Access Option (The Dark Knight theme bypass) */}
          <button
            onClick={handleGuestLogin}
            disabled={loading}
            className="group relative w-full h-11 border border-[#ea580c]/40 hover:border-[#ea580c] bg-[#1a0f08]/30 hover:bg-[#ea580c]/10 text-xs font-mono tracking-[0.18em] uppercase text-[#fcd34d] hover:text-white rounded-sm flex items-center justify-center gap-2 cursor-pointer transition-all duration-300"
          >
            {loading ? (
              <Loader size={14} className="animate-spin text-[#ea580c]" />
            ) : (
              <>
                <Key size={13} className="text-[#ea580c] group-hover:animate-pulse" />
                <span>ACCESS AS GUEST (BRUCE WAYNE)</span>
              </>
            )}
            <div className="absolute inset-x-0 bottom-0 h-[1.5px] bg-gradient-to-r from-transparent via-[#ea580c] to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        </div>

        {error && (
          <div className="w-full text-center border border-[#ef4444]/40 bg-[#1c0c0c]/80 text-[#f87171] font-mono text-[10px] p-2.5 uppercase tracking-wide rounded-sm animate-shake">
            {error}
          </div>
        )}

        {/* Footer info */}
        <div className="flex flex-col items-center gap-2 mt-2 w-full">
          <div className="flex items-center gap-1.5 text-[9px] font-mono text-[#ea580c]/50 uppercase tracking-[0.35em] animate-pulse">
            <Zap size={9} /> Awaiting_Uplink_Authorization
          </div>
          <div className="w-36 h-[1px] bg-gradient-to-r from-transparent via-[#2a2d33] to-transparent" />
          <div className="text-[8px] font-mono text-[#3a3f4a] uppercase tracking-widest text-center">
            SYS_SECURE_LINK // NODE_01 // LVL_7
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
