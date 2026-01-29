import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { SiteData } from '../types';
import { Menu, X, ChevronDown, Flame, Search, ExternalLink, Disc, Twitter, Youtube, Instagram, Video } from 'lucide-react';

interface HeaderProps {
  data: SiteData['header'];
  siteName: string;
  logoPath: string;
}

const Header: React.FC<HeaderProps> = ({ data, siteName, logoPath }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [hoveredTab, setHoveredTab] = useState<string | null>(null);
  const [mobileExpandedTab, setMobileExpandedTab] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleMouseEnter = (label: string) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setHoveredTab(label);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setHoveredTab(null);
    }, 150);
  };

  const toggleMobileTab = (label: string) => {
    setMobileExpandedTab(mobileExpandedTab === label ? null : label);
  };

  const getSocialIcon = (iconId?: string) => {
    switch (iconId) {
      case 'discord': return <Disc className="w-5 h-5" />;
      case 'twitter': return <Twitter className="w-4 h-4" />;
      case 'youtube': return <Youtube className="w-5 h-5" />;
      case 'instagram': return <Instagram className="w-4 h-4" />;
      case 'tiktok': return <Video className="w-4 h-4" />; // Generic video icon fallback
      default: return <ExternalLink className="w-4 h-4" />;
    }
  };

  // Close mobile menu on resize if screen becomes large
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) setIsMobileMenuOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-50 w-full bg-[var(--bg1)]/95 backdrop-blur-md border-b border-[var(--stroke)] shadow-2xl shadow-black/50">
        
        {/* Top Bar */}
        <div className="container mx-auto px-4 h-16 flex items-center gap-4 lg:gap-8 justify-between">
          
          {/* 1. Brand */}
          <Link 
            to="/" 
            className="flex items-center gap-3 flex-shrink-0 group rounded p-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ember)] select-none"
          >
            <img 
              src={logoPath} 
              alt={siteName} 
              className="h-8 w-auto object-contain drop-shadow-[0_0_8px_rgba(210,23,23,0.5)] transition-transform duration-300 group-hover:scale-110" 
            />
            <span className="font-rpg font-bold text-lg tracking-wide text-[var(--text)] group-hover:text-[var(--ember)] transition-colors hidden sm:block">
              {siteName}
            </span>
          </Link>

          {/* 2. Desktop Navigation (Tabs) */}
          <nav className="hidden md:flex items-center h-full" onMouseLeave={handleMouseLeave}>
            {data.nav.map((item) => (
              <div 
                key={item.label}
                className="h-full flex items-center"
                onMouseEnter={() => handleMouseEnter(item.label)}
              >
                {item.type === 'mega' ? (
                  <button
                    className={`
                      relative px-4 h-full flex items-center gap-1 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ember)]
                      ${hoveredTab === item.label ? 'text-[var(--text)] bg-[var(--bg2)]' : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--bg0)]'}
                    `}
                    aria-expanded={hoveredTab === item.label}
                  >
                    {item.label}
                    <ChevronDown className={`w-3 h-3 transition-transform ${hoveredTab === item.label ? 'rotate-180' : ''}`} />
                    <div className={`absolute bottom-0 left-0 w-full h-[2px] bg-[var(--ember)] transition-opacity ${hoveredTab === item.label ? 'opacity-100' : 'opacity-0'}`} />
                  </button>
                ) : (
                  <Link
                    to={item.href || '#'}
                    className="px-4 h-full flex items-center text-sm font-semibold text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--bg0)] transition-colors relative focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ember)]"
                  >
                    {item.label}
                  </Link>
                )}
              </div>
            ))}
          </nav>

          {/* 3. Search & Actions */}
          <div className="flex items-center gap-3 flex-grow md:flex-grow-0 justify-end">
            
            {/* Search Stub */}
            {data.search.enabled && (
               <div className="hidden lg:flex relative group w-64">
                 <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-[var(--muted)]">
                   <Search className="w-4 h-4" />
                 </div>
                 <input 
                   type="text" 
                   placeholder={data.search.placeholder}
                   className="w-full bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--text)] text-sm rounded-sm py-1.5 pl-9 pr-2 focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] placeholder:text-[var(--muted)]/50 transition-all"
                 />
               </div>
            )}

            {/* Social Icons (Limited for Desktop Header to avoid clutter, full list in Mobile/Footer/SocialSection) */}
            <div className="hidden md:flex items-center gap-2 border-l border-[var(--stroke)] pl-3">
               {data.social.slice(0, 3).map(s => (
                 <a 
                   key={s.label} 
                   href={s.href} 
                   target="_blank" 
                   rel="noreferrer" 
                   className="text-[var(--muted)] hover:text-[var(--text)] transition-colors p-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ember)]" 
                   aria-label={s.label}
                 >
                   {getSocialIcon(s.iconId)}
                 </a>
               ))}
            </div>

            {/* CTA Button */}
            <Link
              to={data.ctas.collaborator.href}
              className="hidden md:flex items-center justify-center rounded-sm bg-gradient-to-r from-[var(--flame)] to-[var(--ember)] px-4 py-1.5 text-sm font-bold text-white shadow-[0_0_15px_rgba(210,23,23,0.3)] hover:shadow-[0_0_20px_rgba(210,23,23,0.6)] hover:brightness-110 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--ember)] focus-visible:ring-offset-[var(--bg0)]"
            >
              {data.ctas.collaborator.label}
            </Link>

            {/* Mobile Toggle */}
            <button
              className="md:hidden p-2 text-[var(--text)] hover:bg-[var(--bg2)] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ember)]"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* 4. Mega Menu Dropdown Panel (Desktop) */}
        {data.nav.map((item) => (
          item.type === 'mega' && hoveredTab === item.label && (
            <div 
              key={`${item.label}-panel`}
              className="hidden md:block absolute left-0 top-full w-full bg-[var(--bg1)] border-b border-[var(--stroke)] shadow-xl animate-in fade-in slide-in-from-top-2 duration-200"
              onMouseEnter={() => handleMouseEnter(item.label)}
              onMouseLeave={handleMouseLeave}
            >
              <div className="container mx-auto px-4 py-8 grid grid-cols-4 gap-8">
                {/* Columns */}
                {item.columns?.map((col, idx) => (
                  <div key={idx} className="space-y-4">
                    <h3 className="font-rpg font-bold text-[var(--ember)] text-sm uppercase tracking-widest border-b border-[var(--stroke)] pb-2 mb-2">
                      {col.title}
                    </h3>
                    <ul className="space-y-2">
                      {col.items.map((link) => (
                        <li key={link.label}>
                          <Link 
                            to={link.href}
                            className="text-sm text-[var(--muted)] hover:text-[var(--text)] hover:translate-x-1 transition-all flex items-center gap-2 group focus:outline-none focus-visible:text-[var(--text)] focus-visible:underline"
                          >
                            <span className="w-1 h-1 bg-[var(--stroke)] rounded-full group-hover:bg-[var(--flame)] transition-colors"></span>
                            {link.label}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
                {/* Decorative Side Panel */}
                <div className="col-span-1 p-4 rounded bg-[var(--bg0)] border border-[var(--stroke)] flex flex-col justify-center items-center text-center opacity-70">
                    <Flame className="w-12 h-12 text-[var(--stroke)] mb-2" />
                    <span className="text-xs text-[var(--muted)]">Conteúdo atualizado semanalmente.</span>
                </div>
              </div>
            </div>
          )
        ))}
      </header>

      {/* 5. Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-40 bg-[var(--bg0)] pt-20 px-4 overflow-y-auto animate-in slide-in-from-right duration-300 md:hidden">
          {/* Mobile Search */}
          <div className="mb-6">
             <div className="relative">
               <input 
                  type="text" 
                  placeholder="Buscar..."
                  className="w-full bg-[var(--bg1)] border border-[var(--stroke)] p-3 pl-10 rounded text-[var(--text)] focus:border-[var(--ember)] outline-none"
               />
               <Search className="absolute left-3 top-3.5 w-4 h-4 text-[var(--muted)]" />
             </div>
          </div>

          <nav className="space-y-2">
            {data.nav.map((item) => (
              <div key={item.label} className="border-b border-[var(--stroke)] pb-2">
                {item.type === 'mega' ? (
                  <>
                    <button 
                      onClick={() => toggleMobileTab(item.label)}
                      className="w-full flex justify-between items-center py-3 text-lg font-bold text-[var(--text)] focus:outline-none focus-visible:text-[var(--ember)]"
                    >
                      {item.label}
                      <ChevronDown className={`w-5 h-5 transition-transform ${mobileExpandedTab === item.label ? 'rotate-180' : ''}`} />
                    </button>
                    
                    {mobileExpandedTab === item.label && (
                      <div className="bg-[var(--bg1)] rounded-md p-4 space-y-6 mb-4">
                        {item.columns?.map((col, idx) => (
                           <div key={idx}>
                             <h4 className="text-[var(--ember)] text-xs font-bold uppercase mb-3">{col.title}</h4>
                             <div className="flex flex-col gap-3 pl-2 border-l border-[var(--stroke)]">
                               {col.items.map((link) => (
                                 <Link 
                                   key={link.label} 
                                   to={link.href} 
                                   onClick={() => setIsMobileMenuOpen(false)}
                                   className="text-sm text-[var(--muted)] active:text-[var(--text)] focus:outline-none focus-visible:text-[var(--text)]"
                                 >
                                   {link.label}
                                 </Link>
                               ))}
                             </div>
                           </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <Link 
                    to={item.href || '#'}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="block py-3 text-lg font-bold text-[var(--text)] focus:outline-none focus-visible:text-[var(--ember)]"
                  >
                    {item.label}
                  </Link>
                )}
              </div>
            ))}
          </nav>

          <div className="mt-8 space-y-4">
            <Link
              to={data.ctas.collaborator.href}
              onClick={() => setIsMobileMenuOpen(false)}
              className="block w-full text-center rounded bg-[var(--flame)] py-3 font-bold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ember)]"
            >
              {data.ctas.collaborator.label}
            </Link>
            <Link
              to={data.ctas.catarse.href}
              onClick={() => setIsMobileMenuOpen(false)}
              className="block w-full text-center rounded border border-[var(--stroke)] bg-[var(--bg1)] py-3 font-medium text-[var(--muted)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--text)]"
            >
              {data.ctas.catarse.label}
            </Link>
            
            <div className="flex justify-center gap-6 pt-4">
               {data.social.map(s => (
                 <a 
                   key={s.label} 
                   href={s.href} 
                   className="text-[var(--muted)] p-2 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ember)]"
                 >
                   {getSocialIcon(s.iconId)}
                 </a>
               ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Header;