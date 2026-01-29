
import React from 'react';

export const Step: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="relative pl-10 pb-8 last:pb-0 group">
    <div className="absolute left-[11px] top-8 bottom-0 w-px bg-[var(--stroke)] group-last:hidden" />
    <div className="absolute left-0 top-1 w-6 h-6 rounded-full bg-[var(--bg2)] border-2 border-[var(--ember)] flex items-center justify-center z-10 shadow-[0_0_10px_rgba(242,112,7,0.3)] group-hover:scale-110 transition-transform">
      <div className="w-1.5 h-1.5 rounded-full bg-[var(--ember)]" />
    </div>
    <h4 className="font-rpg text-lg font-bold text-[var(--text)] mb-2 uppercase tracking-wide">{title}</h4>
    <div className="text-sm text-[var(--muted)] leading-relaxed">{children}</div>
  </div>
);

export const Steps: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="my-8">
    {children}
  </div>
);
