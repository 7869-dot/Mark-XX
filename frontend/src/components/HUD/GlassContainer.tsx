import React from 'react';
import { motion } from 'framer-motion';

interface GlassContainerProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

const GlassContainer: React.FC<GlassContainerProps> = ({ children, className = '', delay = 0 }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ 
        type: "spring",
        stiffness: 260,
        damping: 20,
        delay 
      }}
      className={`glass rounded-sm overflow-hidden ${className}`}
    >
      <div className="absolute top-0 left-0 w-1 h-1 border-t border-l border-white/20" />
      <div className="absolute top-0 right-0 w-1 h-1 border-t border-r border-white/20" />
      <div className="absolute bottom-0 left-0 w-1 h-1 border-b border-l border-white/20" />
      <div className="absolute bottom-0 right-0 w-1 h-1 border-b border-r border-white/20" />
      {children}
    </motion.div>
  );
};

export default GlassContainer;
