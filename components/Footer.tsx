import React from 'react';
import { SiteData } from '../types';
import { Github, Twitter, Youtube, Disc } from 'lucide-react';

interface FooterProps {
  data: SiteData['site'];
  social: SiteData['header']['social'];
}

const Footer: React.FC<FooterProps> = ({ data, social }) => {
  const getIcon = (label: string) => {
    const l = label.toLowerCase();
    if (l.includes('discord')) return <Disc className="w-5 h-5" />;
    if (l.includes('youtube')) return <Youtube className="w-5 h-5" />;
    if (l.includes('instagram')) return <span className="font-bold text-sm">IG</span>; // Fallback
    return <span className="font-bold text-sm">{label[0]}</span>;
  };

  return (
    <footer className="border-t border-[var(--stroke)] bg-[var(--bg1)] py-12 mt-16">
      <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="text-center md:text-left">
          <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-2">{data.name}</h3>
          <p className="text-sm text-[var(--muted)] max-w-xs">{data.tagline}</p>
        </div>
        
        <div className="flex gap-4">
          {social.map(s => (
            <a 
              key={s.label}
              href={s.href}
              target="_blank" 
              rel="noreferrer"
              className="p-2 rounded-full bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--ember)] hover:border-[var(--ember)] transition-all"
              aria-label={s.label}
            >
              {getIcon(s.label)}
            </a>
          ))}
        </div>
      </div>
      <div className="container mx-auto px-4 mt-8 pt-8 border-t border-[var(--stroke)] text-center text-xs text-[var(--muted)]">
        <p>© {new Date().getFullYear()} {data.name}. All rights reserved.</p>
        <p className="mt-2 opacity-50">Unofficial showcase MVP.</p>
      </div>
    </footer>
  );
};

export default Footer;