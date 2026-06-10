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
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8, delay, ease: 'easeOut' }}
      className={`glass rounded-xl overflow-hidden ${className}`}
    >
      {children}
    </motion.div>
  );
};

export default GlassContainer;
