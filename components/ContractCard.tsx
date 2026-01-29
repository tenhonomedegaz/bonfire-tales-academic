import React from 'react';
import { ContractCardData } from '../types';
import { Skull, Coins, Sword, Scroll } from 'lucide-react';

interface ContractCardProps {
  data: ContractCardData;
}

const ContractCard: React.FC<ContractCardProps> = ({ data }) => {
  // Determine color based on Rank roughly
  const isHighRank = data.rank.includes('S') || data.rank.includes('A');
  const rankColor = isHighRank ? 'text-[var(--flame)] border-[var(--flame)]' : 'text-[var(--ember)] border-[var(--ember)]';

  return (
    <div className="group relative flex flex-col p-6 rounded-sm bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] transition-all duration-300 overflow-hidden shadow-lg shadow-black/40">
      
      {/* Top Decoration Line */}
      <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[var(--flame)] via-[var(--ember)] to-[var(--bg1)] opacity-70" />
      
      <div className="flex justify-between items-start mb-4">
        <div className={`px-2 py-0.5 border ${rankColor} text-xs font-bold uppercase tracking-widest bg-black/50 backdrop-blur-sm`}>
          {data.rank}
        </div>
        <div className="text-[var(--muted)] text-xs uppercase flex items-center gap-1">
          <Scroll className="w-3 h-3" />
          {data.type}
        </div>
      </div>

      <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-2 group-hover:text-[var(--spark)] transition-colors">
        {data.title}
      </h3>

      <p className="text-sm text-[var(--muted)] mb-6 flex-grow leading-relaxed border-l-2 border-[var(--stroke)] pl-3">
        {data.description}
      </p>

      <div className="mt-auto pt-4 border-t border-[var(--stroke)] flex items-center justify-between text-xs sm:text-sm">
        <div className="flex items-center gap-2 text-[var(--text)] font-medium">
          <Coins className="w-4 h-4 text-[var(--spark)]" />
          {data.reward}
        </div>
        <button className="text-[var(--flame)] hover:text-[var(--text)] font-bold uppercase text-xs tracking-wide transition-colors flex items-center gap-1 group-hover:translate-x-1 duration-300">
          Aceitar
          <Sword className="w-3 h-3" />
        </button>
      </div>

      {/* Hover Glow Effect */}
      <div className="absolute -inset-1 bg-gradient-to-r from-[var(--flame)] to-[var(--ember)] opacity-0 group-hover:opacity-5 blur-xl transition-opacity duration-500 pointer-events-none" />
    </div>
  );
};

export default ContractCard;