import React from 'react';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import { useStore } from '../store/useStore';
import { motion } from 'framer-motion';
import { Shield } from 'lucide-react';

const Login: React.FC = () => {
  const { setToken, setUser } = useStore();

  const handleSuccess = async (credentialResponse: any) => {
    try {
      const backendUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
      const response = await axios.post(`${backendUrl}/auth/google`, {
        credential: credentialResponse.credential
      });
      
      const { access_token } = response.data;
      setToken(access_token);
      
      // Fetch user profile (or decode JWT)
      // For now, we'll assume the token works and the app will fetch details in App.tsx
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-black relative overflow-hidden">
      {/* Background Effect */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-black to-black" />
      
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1 }}
        className="glass p-12 rounded-2xl flex flex-col items-center gap-8 z-10 border-blue-500/20"
      >
        <div className="relative">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            className="w-24 h-24 border-2 border-blue-500/30 border-t-blue-400 rounded-full"
          />
          <div className="absolute inset-0 flex items-center justify-center text-blue-400">
            <Shield size={40} />
          </div>
        </div>

        <div className="text-center">
          <h1 className="text-4xl font-mono font-bold tracking-tighter text-white glow-text uppercase">Axolot // Jarvis</h1>
          <p className="text-slate-500 font-mono text-sm mt-2 uppercase tracking-widest">B2A Network Orchestrator</p>
        </div>

        <div className="w-full">
          <GoogleLogin
            onSuccess={handleSuccess}
            onError={() => console.log('Login Failed')}
            useOneTap
            theme="filled_black"
            shape="pill"
          />
        </div>

        <div className="text-[10px] font-mono text-slate-700 uppercase tracking-widest">
          Authentication Required // Protocol 0-1
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
