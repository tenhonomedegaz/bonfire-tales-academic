
import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  color?: 'ember' | 'flame' | 'muted' | 'success';
}

const Badge: React.FC<BadgeProps> = ({ children, color = 'muted' }) => {
  const colors = {
    ember: 'border-[var(--ember)]/30 text-[var(--ember)] bg-[var(--ember)]/10',
    flame: 'border-[var(--flame)]/30 text-[var(--flame)] bg-[var(--flame)]/10',
    muted: 'border-[var(--stroke)] text-[var(--muted)] bg-[var(--bg2)]',
    success: 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10'
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${colors[color]}`}>
      {children}
    </span>
  );
};

export default Badge;
