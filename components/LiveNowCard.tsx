import React from 'react';
import { LiveNowSection } from '../types';
import { Twitch, Youtube, Radio, ExternalLink } from 'lucide-react';

interface LiveNowCardProps {
  data: LiveNowSection;
}

const LiveNowCard: React.FC<LiveNowCardProps> = ({ data }) => {
  if (!data.enabled) return null;

  const isOnline = data.status === 'online';

  return (
    <div className={`relative overflow-hidden rounded-lg border ${isOnline ? 'border-[var(--flame)] shadow-[0_0_20px_rgba(210,23,23,0.3)]' : 'border-[var(--stroke)]'} bg-[var(--bg1)] transition-all`}>
      
      {/* Background Pulse if Online */}
      {isOnline && (
        <div className="absolute inset-0 bg-gradient-to-r from-[var(--flame)] to-[var(--ember)] opacity-5 animate-pulse" />
      )}

      <div className="relative z-10 p-6 flex flex-col md:flex-row items-center justify-between gap-6">
        
        {/* Status Badge & Info */}
        <div className="flex flex-col gap-2 text-center md:text-left">
          <div className="flex items-center justify-center md:justify-start gap-2">
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-widest ${isOnline ? 'bg-[var(--flame)] text-white animate-pulse' : 'bg-[var(--bg2)] text-[var(--muted)]'}`}>
              <Radio className="w-3 h-3" />
              {isOnline ? 'Ao Vivo' : 'Offline'}
            </span>
            {data.scheduleText && (
              <span className="text-xs text-[var(--muted)] font-mono">
                | {data.scheduleText}
              </span>
            )}
          </div>
          
          <h3 className="font-rpg text-xl font-bold text-[var(--text)]">
            {data.title}
          </h3>
        </div>

        {/* Action Button */}
        <a 
          href={data.href} 
          target="_blank" 
          rel="noreferrer"
          className={`group flex items-center gap-2 px-6 py-3 rounded text-sm font-bold uppercase tracking-wide transition-all ${
            isOnline 
              ? 'bg-[var(--text)] text-[var(--bg0)] hover:scale-105' 
              : 'border border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--text)]'
          }`}
        >
          {data.platform === 'twitch' ? <Twitch className="w-4 h-4" /> : <Youtube className="w-4 h-4" />}
          {isOnline ? 'Assistir Agora' : 'Visitar Canal'}
          {isOnline && <ExternalLink className="w-4 h-4 group-hover:translate-x-1 transition-transform" />}
        </a>
      </div>
    </div>
  );
};

export default LiveNowCard;