import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Dna, 
  Book, 
  Sparkles, 
  Zap, 
  ChevronRight, 
  Loader2, 
  AlertTriangle, 
  Layers, 
  Ruler, 
  Activity, 
  Clock, 
  Ghost,
  Layout,
  ArrowRight,
  XCircle,
  CheckCircle2
} from 'lucide-react';

// --- Types ---

interface Trait {
  name: string;
  text: string;
  bullets?: string[];
}

interface Table {
  title: string;
  headers: string[];
  rows: string[][];
}

interface Talent {
  level: number;
  name: string;
  prerequisites: string;
  effect: string;
  tags: string[];
}

interface Lineage {
  name: string;
  slug: string;
  image?: string;
  description: string;
  traits: Trait[];
}

interface RaceStats {
  creatureType: string;
  size: string;
  speed: string;
  lifespan: string;
}

interface Race {
  name: string;
  slug: string;
  type: 'humanoid' | 'primeval';
  tagline: string;
  stats?: RaceStats;
  images: { base: string };
  lore: {
    presentation: string;
    roleplay: string;
    society: string;
  };
  baseTraits: Trait[];
  lineages: Lineage[];
  allowedEssences: string[];
  racialTalents: Talent[];
}

interface Essence {
  id: string;
  name: string;
  slug: string;
  image?: string;
  lore: {
    presentation: string;
    roleplay: string;
    society: string;
    [key: string]: string;
  };
  traits: Trait[];
  tables?: Table[];
  talents: Talent[];
}

// --- Components ---

const TraitCard: React.FC<{ trait: Trait, colorClass?: string }> = ({ trait, colorClass = "text-[var(--text)]" }) => (
  <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded p-5 mb-4 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
    <h4 className={`font-bold text-lg mb-2 ${colorClass}`}>{trait.name}</h4>
    {trait.text && <p className="text-[var(--muted)] mb-3 leading-relaxed text-sm">{trait.text}</p>}
    {trait.bullets && (
      <ul className="list-disc list-inside space-y-1.5 text-sm text-[var(--muted)] marker:text-[var(--ember)]">
        {trait.bullets.map((b, i) => (
          <li key={i}>{b}</li>
        ))}
      </ul>
    )}
  </div>
);

const TalentCard: React.FC<{ talent: Talent, source: string, sourceColor: string }> = ({ talent, source, sourceColor }) => (
  <div className="bg-[var(--bg2)] border border-[var(--stroke)] rounded p-4 flex flex-col gap-2 hover:border-[var(--muted)] transition-colors h-full relative overflow-hidden group">
    {/* Source Badge */}
    <div className={`absolute top-0 right-0 px-2 py-1 text-[10px] uppercase font-bold tracking-widest rounded-bl ${sourceColor} bg-[var(--bg0)] border-l border-b border-[var(--stroke)]`}>
      {source}
    </div>

    <div className="flex justify-between items-start pr-16">
      <h5 className="font-bold text-[var(--text)] text-base">{talent.name}</h5>
    </div>
    
    <div className="flex gap-1 flex-wrap mb-2">
        {talent.tags.map(tag => (
          <span key={tag} className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--muted)]">
            {tag}
          </span>
        ))}
    </div>

    <div className="text-xs text-[var(--muted)] font-mono border-l-2 border-[var(--stroke)] pl-2 mb-2 opacity-80">
      {talent.prerequisites}
    </div>
    <p className="text-sm text-[var(--muted)] leading-relaxed whitespace-pre-wrap">
      {talent.effect}
    </p>
  </div>
);

const StatBlock: React.FC<{ stats?: RaceStats }> = ({ stats }) => {
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div className="bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)] flex flex-col items-center text-center">
        <Ghost className="w-4 h-4 text-[var(--ember)] mb-1" />
        <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Tipo</span>
        <span className="text-sm font-bold text-[var(--text)]">{stats.creatureType}</span>
      </div>
      <div className="bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)] flex flex-col items-center text-center">
        <Ruler className="w-4 h-4 text-[var(--ember)] mb-1" />
        <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Tamanho</span>
        <span className="text-sm font-bold text-[var(--text)]">{stats.size}</span>
      </div>
      <div className="bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)] flex flex-col items-center text-center">
        <Activity className="w-4 h-4 text-[var(--ember)] mb-1" />
        <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Velocidade</span>
        <span className="text-sm font-bold text-[var(--text)]">{stats.speed}</span>
      </div>
      <div className="bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)] flex flex-col items-center text-center">
        <Clock className="w-4 h-4 text-[var(--ember)] mb-1" />
        <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Vida Média</span>
        <span className="text-sm font-bold text-[var(--text)]">{stats.lifespan}</span>
      </div>
    </div>
  );
};

// --- Main Page ---

const JogadorRaca: React.FC = () => {
  const [races, setRaces] = useState<Race[]>([]);
  const [essences, setEssences] = useState<Essence[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Selection State
  const [selectedRaceSlug, setSelectedRaceSlug] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'traits' | 'lore' | 'talents'>('traits');
  
  // Sub-selection
  const [selectedLineageSlug, setSelectedLineageSlug] = useState<string | null>(null);
  const [selectedEssenceSlug, setSelectedEssenceSlug] = useState<string | null>(null);
  
  // Mobile
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  // 1. Fetch Data
  useEffect(() => {
    Promise.all([
      fetch('/data/races.json').then(r => r.json()),
      fetch('/data/essences.json').then(r => r.json())
    ])
    .then(([racesData, essencesData]) => {
      setRaces(racesData);
      setEssences(essencesData);
      setLoading(false);
    })
    .catch(err => {
      console.error(err);
      setError("Erro ao carregar grimório de raças.");
      setLoading(false);
    });
  }, []);

  // 2. Hash Sync & Default Selection
  useEffect(() => {
    if (loading || races.length === 0) return;
    const hash = window.location.hash.slice(1);
    if (hash) {
      const found = races.find(r => r.slug === hash);
      if (found) {
        setSelectedRaceSlug(found.slug);
        if (window.innerWidth < 768) setIsMobileDetailOpen(true);
      } else {
        setSelectedRaceSlug(races[0].slug);
      }
    } else {
      setSelectedRaceSlug(races[0].slug);
    }
  }, [loading, races]);

  // Derived State
  const activeRace = useMemo(() => races.find(r => r.slug === selectedRaceSlug), [races, selectedRaceSlug]);
  const activeLineage = useMemo(() => activeRace?.lineages.find(l => l.slug === selectedLineageSlug), [activeRace, selectedLineageSlug]);
  const activeEssence = useMemo(() => essences.find(e => e.slug === selectedEssenceSlug), [essences, selectedEssenceSlug]);

  // Determine Image to Show
  const displayImage = useMemo(() => {
    if (activeEssence?.image) return activeEssence.image;
    if (activeLineage?.image) return activeLineage.image;
    return activeRace?.images.base || "";
  }, [activeRace, activeLineage, activeEssence]);

  // Logic Handlers
  const handleSelectRace = (slug: string) => {
    setSelectedRaceSlug(slug);
    window.history.replaceState(null, '', `#${slug}`);
    
    // Reset Sub-selections & Tabs
    setSelectedLineageSlug(null);
    setSelectedEssenceSlug(null);
    setActiveTab('traits'); 

    if (window.innerWidth < 768) {
        setIsMobileDetailOpen(true);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        // On desktop, scroll top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  const handleSelectLineage = (slug: string) => {
    // Direct Swap Logic
    setSelectedLineageSlug(slug);
    setSelectedEssenceSlug(null); // Lineage clears Essence
  };

  const handleSelectEssence = (slug: string) => {
    // Direct Swap Logic
    setSelectedEssenceSlug(slug);
    setSelectedLineageSlug(null); // Essence clears Lineage
  };

  const clearSelection = () => {
    setSelectedLineageSlug(null);
    setSelectedEssenceSlug(null);
  };

  const goToTalents = () => {
    setActiveTab('talents');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // --- Talent Filtering Logic ---
  const getVisibleTalents = (level: number) => {
    if (!activeRace) return [];
    
    const visibleTalents: { talent: Talent, source: string, color: string }[] = [];

    // 1. Race Base Talents
    // Logic: 
    // - If Essence Selected -> Hide talents requiring Lineage. Show general.
    // - If Lineage Selected -> Hide talents requiring Other Lineage. Show General + Specific.
    // - If None Selected -> Show only General.
    const raceTalents = activeRace.racialTalents.filter(t => t.level === level);
    
    raceTalents.forEach(t => {
      const req = t.prerequisites.toLowerCase();
      
      // Determine if talent is bound to ANY lineage of this race
      const requiredLineage = activeRace.lineages.find(lin => req.includes(lin.name.toLowerCase()));
      
      // Determine if talent is bound to ANY essence (unlikely in race list but possible)
      // or specifically mentions "Essência"
      const requiresEssence = req.includes("essência");

      let shouldShow = false;
      let sourceName = "Raça";
      let color = "text-[var(--text)] border-[var(--stroke)]";

      if (activeEssence) {
        // If Essence is active, we hide anything that requires a lineage
        // We show general racial talents
        if (!requiredLineage && !requiresEssence) {
          shouldShow = true;
        }
      } else if (activeLineage) {
        // If Lineage is active
        if (requiredLineage) {
          // Show only if it matches OUR lineage
          if (requiredLineage.slug === activeLineage.slug) {
            shouldShow = true;
            sourceName = "Linhagem";
            color = "text-[var(--ember)] border-[var(--ember)]";
          }
        } else if (!requiresEssence) {
          // Show general racial talents
          shouldShow = true;
        }
      } else {
        // No selection
        // Show only general racial talents
        if (!requiredLineage && !requiresEssence) {
          shouldShow = true;
        }
      }

      if (shouldShow) {
        visibleTalents.push({ talent: t, source: sourceName, color });
      }
    });

    // 2. Essence Talents
    if (activeEssence) {
      const essenceTalents = activeEssence.talents.filter(t => t.level === level);
      essenceTalents.forEach(t => {
        visibleTalents.push({ 
          talent: t, 
          source: "Essência", 
          color: "text-purple-400 border-purple-500" 
        });
      });
    }

    return visibleTalents;
  };

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Carregando raças...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh]">
      <AlertTriangle className="w-10 h-10 text-[var(--flame)] mb-4" />
      <p className="text-[var(--muted)]">{error}</p>
    </div>
  );

  return (
    <main className="min-h-screen bg-[var(--bg0)] pb-12">
      
      {/* Header Bar */}
      <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20 sticky top-16 md:static">
        <div className="container mx-auto max-w-7xl">
          <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Raças & Origens</h1>
          <p className="text-[var(--muted)] text-sm">Escolha sua ascendência biológica ou mágica.</p>
        </div>
      </div>

      <div className="container mx-auto max-w-7xl md:px-4 flex flex-col md:flex-row gap-8 relative mt-4 md:mt-8">
        
        {/* --- SIDEBAR (List) --- */}
        {/* Sticky on Desktop, Hidden on Mobile if Detail is Open */}
        <div className={`
          md:w-72 lg:w-80 shrink-0 flex flex-col
          ${isMobileDetailOpen ? 'hidden md:flex' : 'flex'}
          md:sticky md:top-24 md:self-start md:max-h-[calc(100vh-8rem)] md:overflow-y-auto custom-scrollbar
        `}>
          <div className="space-y-6">
            
            {/* Humanoids */}
            <div>
              <h3 className="text-xs font-bold text-[var(--ember)] uppercase tracking-widest mb-3 pl-2">Raças Humanoides</h3>
              <div className="space-y-1">
                {races.filter(r => r.type === 'humanoid').map(race => (
                  <button
                    key={race.slug}
                    onClick={() => handleSelectRace(race.slug)}
                    className={`w-full text-left px-3 py-3 rounded border transition-all duration-200 flex items-center justify-between gap-2 ${
                      selectedRaceSlug === race.slug
                        ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                        : 'bg-[var(--bg1)] border-transparent hover:bg-[var(--bg2)] hover:border-[var(--stroke)]'
                    }`}
                  >
                    <div className="flex flex-col">
                       <span className={`text-sm font-bold ${selectedRaceSlug === race.slug ? 'text-[var(--text)]' : 'text-[var(--muted)]'}`}>
                         {race.name}
                       </span>
                       <span className="text-[10px] text-[var(--muted)] opacity-70 truncate max-w-[180px]">
                         {race.tagline}
                       </span>
                    </div>
                    {selectedRaceSlug === race.slug && <ChevronRight className="w-4 h-4 text-[var(--ember)]" />}
                  </button>
                ))}
              </div>
            </div>

            {/* Primevals */}
            <div>
              <h3 className="text-xs font-bold text-[var(--text)] uppercase tracking-widest mb-3 pl-2">Raças Primeveras</h3>
              <div className="space-y-1">
                {races.filter(r => r.type === 'primeval').map(race => (
                  <button
                    key={race.slug}
                    onClick={() => handleSelectRace(race.slug)}
                    className={`w-full text-left px-3 py-3 rounded border transition-all duration-200 flex items-center justify-between gap-2 ${
                      selectedRaceSlug === race.slug
                        ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                        : 'bg-[var(--bg1)] border-transparent hover:bg-[var(--bg2)] hover:border-[var(--stroke)]'
                    }`}
                  >
                    <span className={`text-sm font-bold ${selectedRaceSlug === race.slug ? 'text-[var(--text)]' : 'text-[var(--muted)]'}`}>
                      {race.name}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* --- DETAIL PANEL (Content) --- */}
        <div className={`
          flex-1 min-w-0
          ${isMobileDetailOpen ? 'block' : 'hidden md:block'}
        `}>
          
          {/* Mobile Back Button */}
          <div className="md:hidden mb-6 flex items-center gap-3">
             <button onClick={() => setIsMobileDetailOpen(false)} className="text-[var(--text)] p-2 -ml-2 bg-[var(--bg1)] rounded-full border border-[var(--stroke)]">
               <ChevronRight className="w-6 h-6 rotate-180" />
             </button>
             <span className="font-bold text-[var(--text)] text-lg">Voltar para Lista</span>
          </div>

          {activeRace ? (
            <div className="flex flex-col gap-6">
              
              {/* Header inside Panel */}
              <div className="flex flex-col gap-6 border-b border-[var(--stroke)] pb-6">
                <div>
                    <h1 className="font-rpg text-4xl lg:text-5xl font-bold text-[var(--text)] mb-2">{activeRace.name}</h1>
                    <p className="text-lg text-[var(--muted)] italic border-l-2 border-[var(--ember)] pl-4">
                    {activeRace.tagline}
                    </p>
                </div>

                {/* TABS */}
                <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0">
                  <button
                    onClick={() => setActiveTab('traits')}
                    className={`shrink-0 px-6 py-3 text-sm font-bold uppercase tracking-wide border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'traits' ? 'border-[var(--ember)] text-[var(--text)] bg-[var(--bg1)] rounded-t' : 'border-transparent text-[var(--muted)] hover:text-[var(--text)]'}`}
                  >
                    <Dna className="w-4 h-4" /> Regras
                  </button>
                  <button
                    onClick={() => setActiveTab('lore')}
                    className={`shrink-0 px-6 py-3 text-sm font-bold uppercase tracking-wide border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'lore' ? 'border-[var(--ember)] text-[var(--text)] bg-[var(--bg1)] rounded-t' : 'border-transparent text-[var(--muted)] hover:text-[var(--text)]'}`}
                  >
                    <Book className="w-4 h-4" /> Lore
                    {activeEssence && <span className="ml-1 px-1.5 py-0.5 rounded-full bg-purple-900 text-purple-100 text-[10px] border border-purple-500">Essência</span>}
                  </button>
                  <button
                    onClick={() => setActiveTab('talents')}
                    className={`shrink-0 px-6 py-3 text-sm font-bold uppercase tracking-wide border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'talents' ? 'border-[var(--ember)] text-[var(--text)] bg-[var(--bg1)] rounded-t' : 'border-transparent text-[var(--muted)] hover:text-[var(--text)]'}`}
                  >
                    <Zap className="w-4 h-4" /> Talentos
                    {activeEssence && <span className="ml-1 px-1.5 py-0.5 rounded-full bg-purple-900 text-purple-100 text-[10px] border border-purple-500">+</span>}
                  </button>
                </div>
              </div>

              {/* Content Area - Naturally flowing, no fixed height */}
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                
                {/* === TAB: TRAITS (Main View) === */}
                {activeTab === 'traits' && (
                  <div className="pb-20">
                    
                    {/* A) STATS */}
                    <StatBlock stats={activeRace.stats} />

                    {/* B) BASE TRAITS */}
                    <div className="mb-12">
                       <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-6 flex items-center gap-2 border-b border-[var(--stroke)] pb-2">
                         <Dna className="w-6 h-6 text-[var(--ember)]" />
                         Traços da Raça Base
                       </h3>
                       <div className="space-y-4">
                         {activeRace.baseTraits.map((t, i) => <TraitCard key={i} trait={t} />)}
                       </div>
                    </div>

                    {/* C) ANCESTRAL DIVERGENCE (Split Layout) */}
                    <div className="mb-12">
                       <div className="flex items-center justify-between mb-6">
                          <h3 className="font-rpg text-2xl font-bold text-[var(--text)] flex items-center gap-2">
                             <Layout className="w-6 h-6 text-[var(--flame)]" />
                             Divergência Ancestral
                          </h3>
                       </div>

                       <div className="flex flex-col lg:grid lg:grid-cols-12 gap-6 lg:gap-8">
                          
                          {/* LEFT PANEL: SELECTORS */}
                          {/* Mobile: Order 2. Desktop: Order 1. */}
                          <div className="lg:col-span-7 order-2 lg:order-1 flex flex-col gap-4">
                             {activeRace.type === 'humanoid' ? (
                               <div className="text-sm text-[var(--muted)] bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)] mb-2">
                                 <p>
                                   Escolha <strong>uma</strong> opção abaixo. Selecionar uma Linhagem desmarca Essências e vice-versa.
                                 </p>
                               </div>
                             ) : (
                               <p className="text-sm text-[var(--muted)] mb-2 bg-[var(--bg1)] p-3 rounded border border-[var(--stroke)]">
                                 Raças Primeveras escolhem apenas sua Linhagem. Essências não se aplicam.
                               </p>
                             )}

                             {/* LISTS GRID */}
                             <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                
                                {/* COLUMN 1: LINEAGES */}
                                <div className="flex flex-col h-96 bg-[var(--bg0)]/50 rounded border border-[var(--stroke)] p-3">
                                    <div className="flex items-center justify-between border-b border-[var(--stroke)] pb-2 mb-3">
                                      <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--text)]">Linhagens</h4>
                                      {selectedLineageSlug && (
                                        <button onClick={clearSelection} className="text-[10px] uppercase font-bold text-[var(--muted)] hover:text-[var(--flame)] flex items-center gap-1 transition-colors">
                                          <XCircle className="w-3 h-3" /> Limpar
                                        </button>
                                      )}
                                    </div>
                                    
                                    <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                        {activeRace.lineages.map(lin => {
                                          const isSelected = selectedLineageSlug === lin.slug;
                                          return (
                                            <button
                                              key={lin.slug}
                                              onClick={() => handleSelectLineage(lin.slug)}
                                              className={`w-full flex items-center justify-between p-3 rounded border transition-all duration-200 min-h-[40px] text-left group relative overflow-hidden ${
                                                isSelected
                                                  ? 'bg-[var(--bg1)] border-[var(--ember)] ring-1 ring-[var(--ember)]'
                                                  : 'bg-[var(--bg1)] border-[var(--stroke)] hover:border-[var(--muted)]'
                                              } ${selectedEssenceSlug ? 'opacity-50 hover:opacity-100 grayscale' : 'opacity-100'}`}
                                            >
                                              <span className={`font-bold text-xs sm:text-sm leading-tight ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                                                {lin.name}
                                              </span>
                                              {isSelected ? (
                                                <CheckCircle2 className="w-4 h-4 text-[var(--ember)] shrink-0 ml-2" />
                                              ) : (
                                                <div className="w-3 h-3 rounded-full border border-[var(--stroke)] group-hover:border-[var(--muted)] shrink-0 ml-2"></div>
                                              )}
                                            </button>
                                          );
                                        })}
                                        {activeRace.lineages.length === 0 && (
                                            <p className="text-xs text-[var(--muted)] italic p-2">Nenhuma linhagem disponível.</p>
                                        )}
                                    </div>
                                </div>

                                {/* COLUMN 2: ESSENCES */}
                                <div className="flex flex-col h-96 bg-[var(--bg0)]/50 rounded border border-[var(--stroke)] p-3">
                                    <div className="flex items-center justify-between border-b border-[var(--stroke)] pb-2 mb-3">
                                      <h4 className="text-xs font-bold uppercase tracking-widest text-purple-400">Essências</h4>
                                      {selectedEssenceSlug && (
                                        <button onClick={clearSelection} className="text-[10px] uppercase font-bold text-[var(--muted)] hover:text-purple-400 flex items-center gap-1 transition-colors">
                                          <XCircle className="w-3 h-3" /> Limpar
                                        </button>
                                      )}
                                    </div>

                                    <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                                        {activeRace.type === 'humanoid' ? (
                                            <>
                                                {activeRace.allowedEssences.map(slug => {
                                                  const ess = essences.find(e => e.slug === slug);
                                                  if (!ess) return null;
                                                  const isSelected = selectedEssenceSlug === slug;
                                                  return (
                                                    <button
                                                      key={slug}
                                                      onClick={() => handleSelectEssence(slug)}
                                                      className={`w-full flex items-center justify-between p-3 rounded border transition-all duration-200 min-h-[40px] text-left group relative overflow-hidden ${
                                                        isSelected
                                                        ? 'bg-purple-900/10 border-purple-500 ring-1 ring-purple-500'
                                                        : 'bg-[var(--bg1)] border-[var(--stroke)] hover:border-purple-400/50'
                                                      } ${selectedLineageSlug ? 'opacity-50 hover:opacity-100 grayscale' : 'opacity-100'}`}
                                                    >
                                                      <span className={`font-bold text-xs sm:text-sm leading-tight ${isSelected ? 'text-purple-100' : 'text-[var(--muted)] group-hover:text-purple-200'}`}>
                                                        {ess.name}
                                                      </span>
                                                      {isSelected ? (
                                                        <CheckCircle2 className="w-4 h-4 text-purple-400 shrink-0 ml-2" />
                                                      ) : (
                                                        <div className="w-3 h-3 rounded-full border border-[var(--stroke)] group-hover:border-purple-400/50 shrink-0 ml-2"></div>
                                                      )}
                                                    </button>
                                                  );
                                                })}
                                                {activeRace.allowedEssences.length === 0 && (
                                                    <p className="text-xs text-[var(--muted)] italic p-2">Nenhuma essência permitida.</p>
                                                )}
                                            </>
                                        ) : (
                                            <div className="h-full flex items-center justify-center text-center p-4 opacity-50">
                                                <p className="text-xs text-[var(--muted)]">Essências não disponíveis para raças Primeveras.</p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                             </div>
                          </div>

                          {/* RIGHT PANEL: IMAGE */}
                          {/* Mobile: Order 1. Desktop: Order 2. */}
                          <div className="lg:col-span-5 order-1 lg:order-2">
                              <div className="relative aspect-[3/4] md:aspect-[4/3] lg:aspect-[3/4] bg-[var(--bg1)] rounded-lg border border-[var(--stroke)] overflow-hidden shadow-2xl sticky top-24">
                                 <div className="absolute inset-0 bg-cover bg-center transition-all duration-500" style={{ backgroundImage: `url(${displayImage})` }}></div>
                                 <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg0)] to-transparent opacity-90"></div>
                                 
                                 <div className="absolute bottom-0 left-0 p-6">
                                    {activeEssence ? (
                                      <>
                                        <span className="text-purple-400 text-xs font-bold uppercase tracking-widest mb-1 block">Essência Selecionada</span>
                                        <h3 className="font-rpg text-2xl font-bold text-[var(--text)]">{activeEssence.name}</h3>
                                      </>
                                    ) : activeLineage ? (
                                      <>
                                        <span className="text-[var(--ember)] text-xs font-bold uppercase tracking-widest mb-1 block">Linhagem Selecionada</span>
                                        <h3 className="font-rpg text-2xl font-bold text-[var(--text)]">{activeLineage.name}</h3>
                                      </>
                                    ) : (
                                      <>
                                        <span className="text-[var(--muted)] text-xs font-bold uppercase tracking-widest mb-1 block">Raça Base</span>
                                        <h3 className="font-rpg text-2xl font-bold text-[var(--text)]">{activeRace.name}</h3>
                                      </>
                                    )}
                                 </div>
                              </div>
                          </div>

                       </div>
                    </div>

                    {/* D) SPECIFIC TRAITS RENDER */}
                    {activeLineage && (
                      <div className="animate-in fade-in slide-in-from-bottom-4 border-t border-[var(--stroke)] pt-8">
                        <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-4 pb-2">
                          Traços da <span className="text-[var(--ember)]">{activeLineage.name}</span>
                        </h3>
                        {activeLineage.traits.map((t, i) => <TraitCard key={i} trait={t} colorClass="text-[var(--ember)]" />)}
                        
                        {/* Call To Action */}
                        <div className="mt-8 p-6 bg-[var(--bg1)] rounded border border-[var(--stroke)] text-center">
                           <p className="text-[var(--muted)] mb-4">Gostou desta linhagem?</p>
                           <button onClick={goToTalents} className="inline-flex items-center gap-2 px-6 py-3 rounded bg-[var(--ember)] text-white font-bold hover:bg-[var(--flame)] transition-colors shadow-lg">
                             Ver Talentos Disponíveis <ArrowRight className="w-4 h-4"/>
                           </button>
                        </div>
                      </div>
                    )}

                    {activeEssence && (
                      <div className="animate-in fade-in slide-in-from-bottom-4 border-t border-[var(--stroke)] pt-8">
                        <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-4 pb-2">
                          Traços da <span className="text-purple-400">{activeEssence.name}</span>
                        </h3>
                        {activeEssence.traits.map((t, i) => <TraitCard key={i} trait={t} colorClass="text-purple-400" />)}

                        {/* Call To Action */}
                        <div className="mt-8 p-6 bg-purple-900/10 rounded border border-purple-900/30 text-center">
                           <p className="text-purple-200/70 mb-4">A Essência altera fundamentalmente seu personagem.</p>
                           <button onClick={goToTalents} className="inline-flex items-center gap-2 px-6 py-3 rounded bg-purple-600 text-white font-bold hover:bg-purple-700 transition-colors shadow-lg">
                             Ver Talentos de Essência <ArrowRight className="w-4 h-4"/>
                           </button>
                        </div>
                      </div>
                    )}

                  </div>
                )}

                {/* === TAB: LORE === */}
                {activeTab === 'lore' && (
                  <div className="max-w-3xl pb-20">
                    {activeEssence ? (
                      <div className="relative">
                         <div className="absolute -left-4 top-0 bottom-0 w-1 bg-purple-500"></div>
                         <h2 className="font-rpg text-2xl font-bold text-purple-400 mb-6">Lore da Essência: {activeEssence.name}</h2>
                         <div className="prose prose-invert max-w-none text-[var(--muted)] mb-8">
                           <p className="whitespace-pre-wrap leading-relaxed">{activeEssence.lore.presentation}</p>
                         </div>
                         <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)] mb-8">
                           <h3 className="font-bold text-[var(--text)] mb-4 flex items-center gap-2"><Sparkles className="w-4 h-4"/> Roleplay</h3>
                           <p className="whitespace-pre-wrap leading-relaxed text-sm">{activeEssence.lore.roleplay}</p>
                         </div>
                         <div className="prose prose-invert max-w-none text-[var(--muted)]">
                           <h3 className="font-bold text-[var(--text)]">Sociedade</h3>
                           <p className="whitespace-pre-wrap leading-relaxed">{activeEssence.lore.society}</p>
                         </div>
                      </div>
                    ) : (
                      <div>
                        <h2 className="font-rpg text-2xl font-bold text-[var(--text)] mb-6">Lore: {activeRace.name}</h2>
                        <div className="prose prose-invert max-w-none text-[var(--muted)] mb-8">
                           <p className="whitespace-pre-wrap leading-relaxed">{activeRace.lore.presentation}</p>
                        </div>
                        <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)] mb-8">
                           <h3 className="font-bold text-[var(--text)] mb-4 flex items-center gap-2"><Sparkles className="w-4 h-4"/> Roleplay</h3>
                           <p className="whitespace-pre-wrap leading-relaxed text-sm">{activeRace.lore.roleplay}</p>
                        </div>
                        <div className="prose prose-invert max-w-none text-[var(--muted)]">
                           <h3 className="font-bold text-[var(--text)]">Sociedade</h3>
                           <p className="whitespace-pre-wrap leading-relaxed">{activeRace.lore.society}</p>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* === TAB: TALENTS === */}
                {activeTab === 'talents' && (
                  <div className="max-w-4xl pb-20">
                    <p className="text-[var(--muted)] mb-8 p-4 bg-[var(--bg1)] border border-[var(--stroke)] rounded text-sm">
                      <strong className="text-[var(--text)] block mb-1">Sobre Talentos Raciais</strong>
                      Estes talentos podem ser escolhidos nos níveis indicados (1, 5, 9, 13, 17) para substituir talentos de classe, permitindo que seu personagem evolua sua biologia ou natureza mágica.
                      
                      {activeEssence && (
                        <span className="block mt-2 text-purple-400 font-bold border-t border-[var(--stroke)] pt-2">
                          Visualizando talentos da Essência selecionada. Talentos de linhagem específica foram ocultados.
                        </span>
                      )}
                      
                      {activeLineage && (
                        <span className="block mt-2 text-[var(--ember)] font-bold border-t border-[var(--stroke)] pt-2">
                          Visualizando talentos para {activeLineage.name}.
                        </span>
                      )}
                    </p>

                    {[1, 5, 9, 13, 17].map(level => {
                      const visibleTalents = getVisibleTalents(level);

                      if (visibleTalents.length === 0) return null;

                      return (
                        <div key={level} className="mb-10">
                          <div className="flex items-center gap-4 mb-6">
                            <span className="font-rpg font-bold text-[var(--text)] text-xl border border-[var(--stroke)] px-3 py-1 rounded bg-[var(--bg1)]">
                              Nível {level}
                            </span>
                            <div className="h-px bg-[var(--stroke)] flex-1"></div>
                          </div>
                          <div className="grid md:grid-cols-2 gap-6">
                            {visibleTalents.map((item, i) => (
                              <TalentCard 
                                key={i} 
                                talent={item.talent} 
                                source={item.source} 
                                sourceColor={item.color} 
                              />
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
             <div className="flex flex-col items-center justify-center h-96 text-[var(--muted)] opacity-50">
               <Book className="w-16 h-16 mb-4" />
               <p>Selecione uma raça no grimório à esquerda.</p>
             </div>
          )}
        </div>
      </div>
    </main>
  );
};

export default JogadorRaca;