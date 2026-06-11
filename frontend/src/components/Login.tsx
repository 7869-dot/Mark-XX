import React, { useState, useMemo } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import axios from 'axios';
import { useStore } from '../store/useStore';
import { motion } from 'framer-motion';
import { Lock, Terminal, Key, Loader, Zap, ShieldAlert, Radio } from 'lucide-react';

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

  // Generate rain drops with stable random values
  const rainDrops = useMemo(() => Array.from({ length: 80 }, (_, i) => ({
    id: i,
    left: (i * 1.25) % 100,
    delay: (i * 0.137) % 3,
    duration: 0.6 + (i * 0.031) % 0.8,
    height: 12 + (i * 3.7) % 20,
    opacity: 0.08 + (i * 0.007) % 0.15,
  })), []);

  // Floating ember particles
  const embers = useMemo(() => Array.from({ length: 25 }, (_, i) => ({
    id: i,
    size: 1.5 + (i * 0.47) % 3,
    left: (i * 4.1) % 100,
    delay: (i * 0.6) % 5,
    duration: 5 + (i * 0.8) % 6,
  })), []);

  // Gotham buildings skyline
  const buildings = useMemo(() => [
    { x: 0, w: 45, h: 180, windows: 6 },
    { x: 40, w: 35, h: 250, windows: 9 },
    { x: 70, w: 55, h: 210, windows: 7 },
    { x: 120, w: 40, h: 310, windows: 11 },
    { x: 155, w: 50, h: 270, windows: 10 },
    { x: 200, w: 38, h: 190, windows: 7 },
    { x: 233, w: 60, h: 340, windows: 12 },
    { x: 288, w: 42, h: 220, windows: 8 },
    { x: 325, w: 55, h: 290, windows: 10 },
    { x: 375, w: 48, h: 200, windows: 7 },
    { x: 418, w: 35, h: 260, windows: 9 },
    { x: 448, w: 65, h: 330, windows: 12 },
    { x: 508, w: 40, h: 180, windows: 6 },
    { x: 543, w: 50, h: 240, windows: 8 },
    { x: 588, w: 45, h: 300, windows: 11 },
    { x: 628, w: 55, h: 210, windows: 7 },
    { x: 678, w: 42, h: 350, windows: 13 },
    { x: 715, w: 60, h: 270, windows: 9 },
    { x: 770, w: 38, h: 190, windows: 6 },
    { x: 803, w: 50, h: 320, windows: 11 },
    { x: 848, w: 45, h: 230, windows: 8 },
    { x: 888, w: 55, h: 280, windows: 10 },
    { x: 938, w: 40, h: 200, windows: 7 },
    { x: 973, w: 48, h: 310, windows: 11 },
  ], []);

  return (
    <div className="login-scene">
      {/* Film grain overlay */}
      <div className="login-grain" />
      
      {/* Dark moody sky gradient */}
      <div className="login-sky" />

      {/* Bat Signal beam in the clouds */}
      <div className="bat-signal-beam">
        <motion.div 
          className="bat-signal-glow"
          animate={{ 
            opacity: [0.3, 0.6, 0.4, 0.7, 0.3],
            scale: [1, 1.05, 0.98, 1.03, 1],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        >
          <svg viewBox="0 0 200 140" className="bat-signal-svg">
            <path d="M 100,20 C 102,20 104,22 106,25 C 109,29 111,32 113,32 C 115,32 116,29 119,25 C 121,22 123,20 125,20 C 127,20 128,21 129,23 C 132,27 135,32 138,36 C 145,46 153,53 162,58 C 172,63 182,65 192,65 C 196,65 200,64 200,64 C 200,64 195,68 188,73 C 180,78 171,85 163,94 C 158,100 154,106 150,113 C 148,116 146,120 145,120 C 144,120 142,118 139,114 C 134,107 127,101 120,96 C 114,92 107,89 100,88 C 93,89 86,92 80,96 C 73,101 66,107 61,114 C 58,118 56,120 55,120 C 54,120 52,116 50,113 C 46,106 42,100 37,94 C 29,85 20,78 12,73 C 5,68 0,64 0,64 C 0,64 4,65 8,65 C 18,65 28,63 38,58 C 47,53 55,46 62,36 C 65,32 68,27 71,23 C 72,21 73,20 75,20 C 77,20 79,22 81,25 C 84,29 85,32 87,32 C 89,32 91,29 94,25 C 96,22 98,20 100,20 Z" />
          </svg>
        </motion.div>
        {/* Volumetric light cone */}
        <div className="bat-signal-cone" />
      </div>

      {/* Gotham City Skyline */}
      <div className="gotham-skyline">
        <svg viewBox="0 0 1024 400" preserveAspectRatio="none" className="skyline-svg">
          <defs>
            <linearGradient id="buildingGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#0c0e14" />
              <stop offset="100%" stopColor="#020304" />
            </linearGradient>
            <linearGradient id="windowGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ea580c" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.2" />
            </linearGradient>
          </defs>
          {buildings.map((b, i) => (
            <g key={i}>
              <rect 
                x={b.x} y={400 - b.h} width={b.w} height={b.h}
                fill="url(#buildingGrad)"
                stroke="#1a1c24"
                strokeWidth="0.5"
              />
              {/* Windows */}
              {Array.from({ length: b.windows }).map((_, wi) => {
                const cols = Math.floor(b.w / 12);
                const row = Math.floor(wi / Math.max(cols, 1));
                const col = wi % Math.max(cols, 1);
                const wy = 400 - b.h + 15 + row * 28;
                const wx = b.x + 6 + col * 12;
                const lit = (i + wi) % 3 !== 0;
                return (
                  <rect
                    key={wi}
                    x={wx} y={wy} width="5" height="8"
                    fill={lit ? "url(#windowGlow)" : "#0a0c10"}
                    opacity={lit ? 0.4 + ((i + wi) % 5) * 0.1 : 0.3}
                  >
                    {lit && (
                      <animate
                        attributeName="opacity"
                        values={`${0.2 + ((i + wi) % 4) * 0.1};${0.5 + ((i + wi) % 3) * 0.15};${0.3 + ((i + wi) % 5) * 0.1}`}
                        dur={`${3 + (i + wi) % 5}s`}
                        repeatCount="indefinite"
                      />
                    )}
                  </rect>
                );
              })}
            </g>
          ))}
        </svg>
      </div>

      {/* Rain particle system */}
      <div className="rain-container">
        {rainDrops.map((drop) => (
          <div
            key={drop.id}
            className="rain-drop"
            style={{
              left: `${drop.left}%`,
              animationDelay: `${drop.delay}s`,
              animationDuration: `${drop.duration}s`,
              height: `${drop.height}px`,
              opacity: drop.opacity,
            }}
          />
        ))}
      </div>

      {/* Floating ember particles */}
      <div className="ember-container">
        {embers.map((emb) => (
          <motion.div
            key={emb.id}
            className="ember-particle"
            style={{
              width: emb.size,
              height: emb.size,
              left: `${emb.left}%`,
              bottom: '-5px',
            }}
            animate={{
              y: ['0vh', '-100vh'],
              x: ['0px', `${((emb.id * 7) % 60) - 30}px`],
              opacity: [0, 0.7, 0],
              scale: [1, 1.4, 0.3],
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

      {/* Scanning line effect */}
      <div className="login-scanline" />

      {/* Vignette overlay */}
      <div className="login-vignette" />

      {/* ═══════════ MAIN LOGIN CARD ═══════════ */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1.2, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.3 }}
        className="login-card"
      >
        {/* Corner tactical brackets */}
        <div className="card-corner card-corner-tl" />
        <div className="card-corner card-corner-tr" />
        <div className="card-corner card-corner-bl" />
        <div className="card-corner card-corner-br" />

        {/* Top accent line */}
        <div className="card-top-accent" />

        {/* ── Header Section ── */}
        <motion.div
          initial={{ opacity: 0, y: -15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.6 }}
          className="login-header"
        >
          {/* Bat symbol */}
          <div className="header-bat-symbol">
            <svg viewBox="0 0 200 140" className="header-bat-svg">
              <path d="M 100,20 C 102,20 104,22 106,25 C 109,29 111,32 113,32 C 115,32 116,29 119,25 C 121,22 123,20 125,20 C 127,20 128,21 129,23 C 132,27 135,32 138,36 C 145,46 153,53 162,58 C 172,63 182,65 192,65 C 196,65 200,64 200,64 C 200,64 195,68 188,73 C 180,78 171,85 163,94 C 158,100 154,106 150,113 C 148,116 146,120 145,120 C 144,120 142,118 139,114 C 134,107 127,101 120,96 C 114,92 107,89 100,88 C 93,89 86,92 80,96 C 73,101 66,107 61,114 C 58,118 56,120 55,120 C 54,120 52,116 50,113 C 46,106 42,100 37,94 C 29,85 20,78 12,73 C 5,68 0,64 0,64 C 0,64 4,65 8,65 C 18,65 28,63 38,58 C 47,53 55,46 62,36 C 65,32 68,27 71,23 C 72,21 73,20 75,20 C 77,20 79,22 81,25 C 84,29 85,32 87,32 C 89,32 91,29 94,25 C 96,22 98,20 100,20 Z" />
            </svg>
          </div>

          {/* Title */}
          <h1 className="login-title">WAYNE-NET</h1>
          <div className="login-subtitle">
            <Terminal size={10} className="login-subtitle-icon" />
            <span>SECURE_TACTICAL_PORTAL</span>
          </div>

          {/* Status indicators */}
          <motion.div 
            className="login-status-row"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2, duration: 0.8 }}
          >
            <div className="status-indicator">
              <div className="status-dot status-dot-live" />
              <span>ENCRYPTION_ACTIVE</span>
            </div>
            <div className="status-divider" />
            <div className="status-indicator">
              <Radio size={8} className="status-radio-icon" />
              <span>FREQ_LOCKED</span>
            </div>
          </motion.div>
        </motion.div>

        {/* ── Auth Section ── */}
        <motion.div 
          className="login-auth-section"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.9, duration: 0.8 }}
        >
          {/* Google OAuth box */}
          <div className="oauth-container">
            <div className="oauth-accent-line" />
            <div className="oauth-label">
              <Lock size={11} className="oauth-lock-icon" />
              <span>Protocol: OAuth_Credential</span>
            </div>
            <div className="oauth-button-wrapper">
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

          {/* Divider */}
          <div className="auth-divider">
            <div className="auth-divider-line" />
            <span className="auth-divider-text">OR</span>
            <div className="auth-divider-line" />
          </div>

          {/* Guest access button */}
          <motion.button
            onClick={handleGuestLogin}
            disabled={loading}
            className="guest-button"
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
          >
            {loading ? (
              <Loader size={15} className="guest-button-loader" />
            ) : (
              <>
                <Key size={14} className="guest-button-icon" />
                <span className="guest-button-text">ACCESS AS GUEST — BRUCE WAYNE</span>
              </>
            )}
            <div className="guest-button-glow" />
          </motion.button>
        </motion.div>

        {/* Error display */}
        {error && (
          <motion.div 
            className="login-error"
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <ShieldAlert size={12} />
            <span>{error}</span>
          </motion.div>
        )}

        {/* ── Footer ── */}
        <motion.div 
          className="login-footer"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5, duration: 1 }}
        >
          <div className="footer-awaiting">
            <Zap size={9} />
            <span>Awaiting_Uplink_Authorization</span>
          </div>
          <div className="footer-line" />
          <div className="footer-sys-info">
            SYS_SECURE_LINK // NODE_01 // CLEARANCE_LVL_7
          </div>
          <div className="footer-classification">
            <ShieldAlert size={8} />
            <span>WAYNE ENTERPRISES — CLASSIFIED</span>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default Login;
