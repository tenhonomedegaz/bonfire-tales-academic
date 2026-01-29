import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  BookOpen, 
  Loader2, 
  AlertTriangle, 
  X, 
  ChevronLeft, 
  ChevronRight,
  Scroll,
  Info,
  Check,
  MousePointerClick,
  XCircle
} from 'lucide-react';

// --- Types ---

interface Background {
  name: string;
  slug: string;
  tags: string[];
  requirements?: { pantheon?: boolean; reino?: boolean; deus?: boolean };
  description: string;
  ability: {
    name: string;
    effect: string;
  };
}

// --- Components ---

const FilterModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  options: string[];
  selectedOptions: string[];
  onApply: (tags: string[]) => void;
}> = ({ isOpen, onClose, options, selectedOptions, onApply }) => {
  const [localSelected, setLocalSelected] = useState<string[]>(selectedOptions);

  useEffect(() => {
    if (isOpen) setLocalSelected(selectedOptions);
  }, [isOpen, selectedOptions]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose} />
      <div className="relative w-full max-w-md bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="p-4 border-b border-[var(--stroke)] flex justify-between items-center bg-[var(--bg2)]">
          <h3 className="font-rpg text-lg font-bold text-[var(--text)] flex items-center gap-2">
            <Filter className="w-4 h-4 text-[var(--ember)]" />
            Filtrar por Tags
          </h3>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-2">
            {options.map(tag => {
              const isSelected = localSelected.includes(tag);
              return (
                <label key={tag} className={`flex items-center gap-3 p-3 rounded cursor-pointer transition-colors border ${isSelected ? 'bg-[var(--bg2)] border-[var(--ember)]' : 'bg-[var(--bg0)] border-transparent hover:border-[var(--stroke)]'}`}>
                  <div className={`w-4 h-4 rounded flex items-center justify-center border transition-colors ${isSelected ? 'bg-[var(--ember)] border-[var(--ember)]' : 'border-[var(--muted)] bg-[var(--bg1)]'}`}>
                    {isSelected && <Check className="w-3 h-3 text-white" />}
                  </div>
                  <input type="checkbox" className="hidden" checked={isSelected} onChange={() => isSelected ? setLocalSelected(prev => prev.filter(t => t !== tag)) : setLocalSelected(prev => [...prev, tag])} />
                  <span className={`text-xs font-bold uppercase tracking-wide ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)]'}`}>{tag}</span>
                </label>
              );
            })}
          </div>
        </div>
        <div className="p-4 border-t border-[var(--stroke)] bg-[var(--bg2)] flex gap-3">
          <button onClick={() => { onApply(localSelected); onClose(); }} className="flex-1 py-2.5 bg-[var(--ember)] hover:bg-[var(--flame)] text-white font-bold rounded shadow-lg shadow-orange-900/20 transition-all">Aplicar</button>
          <button onClick={() => setLocalSelected([])} className="px-4 py-2.5 border border-[var(--stroke)] bg-[var(--bg1)] text-[var(--muted)] hover:text-[var(--text)] font-bold rounded transition-colors">Limpar</button>
        </div>
      </div>
    </div>
  );
};

const RulesHeader: React.FC = () => (
  <div className="bg-[var(--bg0)] border-b border-[var(--stroke)] py-6">
    <div className="container mx-auto max-w-7xl px-4">
      <div className="mb-4">
        <h1 className="font-rpg text-2xl md:text-3xl font-bold text-[var(--text)] mb-1">Antecedentes</h1>
        <p className="text-sm text-[var(--muted)] italic">Escolha um passado que define seus recursos iniciais e uma habilidade única.</p>
      </div>

      <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg p-4 md:p-5 shadow-sm">
        <h2 className="font-rpg text-base md:text-lg font-bold text-[var(--ember)] mb-3 flex items-center gap-2">
          <BookOpen className="w-4 h-4" /> Regras Gerais de Antecedentes
        </h2>
        <div className="text-[var(--muted)] leading-relaxed text-xs md:text-sm">
          <p className="mb-3">
            Os antecedentes do Bonfire Tales são utilizados de forma padronizada, o que faz com que você como jogador tenha uma liberdade maior de escolha de itens e outros apetrechos durante a criação.
            Todo Antecedente concede benefícios básicos ao seu personagem:
          </p>
          
          <div className="grid md:grid-cols-2 gap-x-8 gap-y-1">
            <ul className="space-y-1 list-none pl-0">
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Atributos:</strong> +2 em um e +1 em outro.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Perícias:</strong> Escolha 2 à sua escolha.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Idiomas/Ferramentas:</strong> Escolha 2 no total.</span>
              </li>
            </ul>
            <ul className="space-y-1 list-none pl-0">
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Equipamentos:</strong> 100 PO (min. 50 PO em itens).</span>
              </li>
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Habilidade Única:</strong> Conforme listado abaixo.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-[var(--ember)] font-bold">•</span>
                <span><strong className="text-[var(--text)]">Talento:</strong> Escolha 1 Talento de Origem.</span>
              </li>
            </ul>
          </div>

          <div className="mt-3 pt-3 border-t border-[var(--stroke)] flex items-start gap-2 text-xs opacity-80">
            <Info className="w-3 h-3 mt-0.5 text-[var(--spark)] shrink-0" /> 
            <p>Alguns antecedentes também pedem que você escolha uma <strong className="text-[var(--text)]">Origem de Nascimento (Reino)</strong> ou um <strong className="text-[var(--text)]">Deus</strong> para definir detalhes do seu Talento de Origem ou requisitos de roleplay.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
);

const DetailPlaceholder: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-[400px] border border-dashed border-[var(--stroke)] rounded-lg bg-[var(--bg1)]/30 text-center p-8 animate-in fade-in">
    <div className="w-16 h-16 rounded-full bg-[var(--bg2)] flex items-center justify-center mb-4 border border-[var(--stroke)]">
      <MousePointerClick className="w-8 h-8 text-[var(--muted)]" />
    </div>
    <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-2">Detalhes do Antecedente</h3>
    <p className="text-[var(--muted)] max-w-xs">
      Selecione um antecedente na lista ao lado para visualizar sua descrição completa e habilidade mecânica.
    </p>
  </div>
);

// --- Main Page ---

const JogadorAntecedentes: React.FC = () => {
  const [data, setData] = useState<Background[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  
  // Selection
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  // Refs
  const detailRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // 1. Fetch Data
  useEffect(() => {
    fetch('/data/backgrounds.json')
      .then(res => {
        if (!res.ok) throw new Error("Falha ao carregar antecedentes.");
        return res.json();
      })
      .then(jsonData => {
        setData(jsonData);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError("Não foi possível carregar o grimório de antecedentes.");
        setLoading(false);
      });
  }, []);

  // 2. Extract Tags
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    data.forEach(bg => bg.tags.forEach(t => tags.add(t)));
    return Array.from(tags).sort();
  }, [data]);

  // 3. Filter & Sort Logic
  const filteredData = useMemo(() => {
    let result = [...data];

    // Search
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      result = result.filter(bg => 
        bg.name.toLowerCase().includes(q) ||
        bg.description.toLowerCase().includes(q) ||
        bg.ability.name.toLowerCase().includes(q) ||
        bg.tags.some(t => t.toLowerCase().includes(q))
      );
    }

    // Tags (AND logic - must have all selected)
    if (selectedTags.length > 0) {
      result = result.filter(bg => 
        selectedTags.every(tag => bg.tags.includes(tag))
      );
    }

    // Sort
    result.sort((a, b) => sortOrder === 'asc' 
      ? a.name.localeCompare(b.name)
      : b.name.localeCompare(a.name)
    );

    return result;
  }, [data, searchTerm, selectedTags, sortOrder]);

  // 4. Selection Handler
  const handleSelect = (slug: string) => {
    setSelectedSlug(slug);
    // On mobile, open detail view
    if (window.innerWidth < 768) {
      setIsMobileDetailOpen(true);
    } else {
      // On desktop, maybe scroll detail to top slightly if needed, but not strictly required
    }
  };

  const handleClearSelection = () => {
    setSelectedSlug(null);
  };

  // Active Item
  const activeBackground = useMemo(() => 
    data.find(bg => bg.slug === selectedSlug), 
  [data, selectedSlug]);

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Consultando arquivos...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <AlertTriangle className="w-10 h-10 text-[var(--flame)]" />
      <p className="text-[var(--muted)]">{error}</p>
    </div>
  );

  return (
    <main className="min-h-screen bg-[var(--bg0)] flex flex-col">
      
      {/* --- Section 1: Rules Header (Scrolls naturally) --- */}
      <RulesHeader />

      {/* --- Section 2: Toolbar (Sticky) --- */}
      <div className="sticky top-16 z-30 bg-[var(--bg0)]/95 backdrop-blur border-b border-[var(--stroke)] shadow-lg">
        <div className="container mx-auto max-w-7xl px-4 py-4">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-grow">
              <input 
                type="text" 
                placeholder="Buscar antecedente, habilidade, frase..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[var(--bg1)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none transition-all"
              />
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
            </div>
            
            <div className="flex gap-2 shrink-0">
               <button onClick={() => setIsFilterModalOpen(true)} className={`flex items-center gap-2 px-3 py-2 rounded border text-sm font-medium transition-colors ${selectedTags.length > 0 ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)]' : 'bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)]'}`}>
                 <Filter className="w-4 h-4" />
                 <span className="hidden sm:inline">Filtros</span>
                 {selectedTags.length > 0 && <span className="bg-[var(--ember)] text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center">{selectedTags.length}</span>}
               </button>
               
               <div className="flex rounded border border-[var(--stroke)] bg-[var(--bg1)] overflow-hidden">
                 <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--bg2)] transition-colors text-sm font-medium border-r border-[var(--stroke)]">
                   <ArrowUpDown className="w-4 h-4" />
                   <span className="hidden sm:inline">{sortOrder === 'asc' ? 'A-Z' : 'Z-A'}</span>
                 </button>
                 {selectedSlug && (
                   <button onClick={handleClearSelection} className="flex items-center gap-1 px-3 py-2 text-[var(--muted)] hover:text-[var(--flame)] hover:bg-[var(--bg2)] transition-colors text-sm font-medium" title="Limpar seleção">
                     <XCircle className="w-4 h-4" />
                   </button>
                 )}
               </div>
            </div>
          </div>

          {selectedTags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {selectedTags.map(tag => (
                <button key={tag} onClick={() => setSelectedTags(prev => prev.filter(t => t !== tag))} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[var(--bg2)] border border-[var(--ember)] text-[var(--muted)] hover:text-white group">
                  {tag} <span className="group-hover:text-[var(--flame)] font-bold">×</span>
                </button>
              ))}
              <button onClick={() => setSelectedTags([])} className="text-xs text-[var(--muted)] hover:text-[var(--text)] underline px-2">Limpar</button>
            </div>
          )}
        </div>
      </div>

      {/* --- Section 3: Master Detail Layout --- */}
      <div className="container mx-auto max-w-7xl px-4 py-8 flex-1 flex flex-col md:flex-row gap-8 relative">
        
        {/* Left Col: List (Sticky) */}
        <div className="w-full md:w-80 lg:w-96 flex-shrink-0 flex flex-col md:sticky md:top-40 self-start max-h-[calc(100vh-10rem)] md:overflow-y-auto custom-scrollbar pr-1">
           <div className="space-y-1" ref={listRef}>
             {filteredData.length > 0 ? (
               filteredData.map(bg => {
                 const isSelected = selectedSlug === bg.slug;
                 return (
                   <button
                     key={bg.slug}
                     onClick={() => handleSelect(bg.slug)}
                     className={`w-full text-left px-4 py-3 rounded border transition-all duration-200 group flex flex-col gap-2 ${
                       isSelected 
                         ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                         : 'bg-[var(--bg1)] border-[var(--stroke)] hover:bg-[var(--bg2)] hover:border-[var(--muted)]'
                     }`}
                   >
                     <div className="flex justify-between items-center w-full">
                        <span className={`text-sm font-bold truncate ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                          {bg.name}
                        </span>
                        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border border-[var(--stroke)] bg-[var(--bg0)] text-[var(--muted)] whitespace-nowrap`}>
                          {bg.tags[0]}
                        </span>
                     </div>
                     {bg.tags.length > 1 && (
                       <div className="flex gap-1 overflow-hidden">
                          {bg.tags.slice(1, 3).map(t => (
                            <span key={t} className="text-[9px] text-[var(--muted)] opacity-70 bg-[var(--bg0)] px-1 rounded">
                              {t}
                            </span>
                          ))}
                       </div>
                     )}
                   </button>
                 );
               })
             ) : (
               <div className="text-center py-10 text-[var(--muted)] text-sm px-4 border border-dashed border-[var(--stroke)] rounded bg-[var(--bg1)]">
                 Nenhum antecedente encontrado.
               </div>
             )}
           </div>
        </div>

        {/* Right Col: Detail (or Placeholder) */}
        <div className="hidden md:block flex-1 min-w-0" ref={detailRef}>
           {activeBackground ? (
             <div className="bg-[var(--bg0)] border border-[var(--stroke)] rounded-lg p-8 animate-in fade-in duration-300 shadow-xl">
                {/* Header */}
                <div className="mb-8 border-b border-[var(--stroke)] pb-6">
                  <div className="flex flex-wrap gap-2 mb-4">
                     {activeBackground.tags.map(tag => (
                       <span key={tag} className="text-xs font-bold uppercase tracking-wider px-2 py-1 rounded border border-[var(--ember)] text-[var(--ember)] bg-[var(--ember)]/10">
                         {tag}
                       </span>
                     ))}
                  </div>
                  <h1 className="font-rpg text-4xl font-bold text-[var(--text)] mb-2">{activeBackground.name}</h1>
                </div>

                {/* Lore */}
                <div className="prose prose-invert max-w-none mb-10 text-[var(--muted)] leading-relaxed whitespace-pre-wrap">
                  {activeBackground.description}
                </div>

                {/* Requirements Alert */}
                {activeBackground.requirements && (
                  <div className="mb-8 flex gap-4">
                     {activeBackground.requirements.pantheon && (
                        <div className="px-3 py-1 rounded bg-blue-900/20 border border-blue-800 text-blue-200 text-xs font-bold uppercase flex items-center gap-2">
                          <BookOpen className="w-3 h-3" /> Requer Panteão
                        </div>
                     )}
                     {activeBackground.requirements.reino && (
                        <div className="px-3 py-1 rounded bg-yellow-900/20 border border-yellow-800 text-yellow-200 text-xs font-bold uppercase flex items-center gap-2">
                          <Scroll className="w-3 h-3" /> Requer Reino de Origem
                        </div>
                     )}
                  </div>
                )}

                {/* Ability Card */}
                <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg p-6 relative overflow-hidden group hover:border-[var(--ember)] transition-colors shadow-lg">
                   <div className="absolute top-0 left-0 w-1 h-full bg-[var(--ember)]"></div>
                   <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-4 flex items-center gap-2">
                     <Scroll className="w-6 h-6 text-[var(--ember)]" />
                     Habilidade: {activeBackground.ability.name}
                   </h3>
                   <p className="text-[var(--text)] text-sm leading-relaxed border-t border-[var(--stroke)] pt-4">
                     {activeBackground.ability.effect}
                   </p>
                </div>

             </div>
           ) : (
             <DetailPlaceholder />
           )}
        </div>

      </div>

      {/* --- Mobile Detail Drawer --- */}
      {isMobileDetailOpen && activeBackground && (
        <div className="fixed inset-0 z-50 md:hidden bg-[var(--bg0)] flex flex-col animate-in slide-in-from-bottom duration-300">
           {/* Header */}
           <div className="flex items-center justify-between p-4 border-b border-[var(--stroke)] bg-[var(--bg1)]">
             <button onClick={() => setIsMobileDetailOpen(false)} className="flex items-center gap-2 text-[var(--muted)] hover:text-[var(--text)]">
               <ChevronLeft className="w-5 h-5" />
               <span className="font-bold uppercase text-xs tracking-wider">Voltar</span>
             </button>
             <div className="flex gap-2">
               <button className="p-2" onClick={() => {
                  const idx = filteredData.findIndex(i => i.slug === selectedSlug);
                  if (idx > 0) handleSelect(filteredData[idx - 1].slug);
               }}>
                  <ChevronLeft className="w-5 h-5 text-[var(--text)]" />
               </button>
               <button className="p-2" onClick={() => {
                  const idx = filteredData.findIndex(i => i.slug === selectedSlug);
                  if (idx < filteredData.length - 1) handleSelect(filteredData[idx + 1].slug);
               }}>
                  <ChevronRight className="w-5 h-5 text-[var(--text)]" />
               </button>
             </div>
           </div>

           {/* Content */}
           <div className="flex-1 overflow-y-auto p-6">
              <div className="mb-6">
                 <div className="flex flex-wrap gap-2 mb-3">
                   {activeBackground.tags.map(tag => (
                     <span key={tag} className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border border-[var(--ember)] text-[var(--ember)] bg-[var(--ember)]/10">
                       {tag}
                     </span>
                   ))}
                 </div>
                 <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-4">{activeBackground.name}</h2>
                 <p className="text-sm text-[var(--muted)] whitespace-pre-wrap leading-relaxed">
                   {activeBackground.description}
                 </p>
              </div>

              <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded p-5 relative mt-8">
                 <div className="absolute -top-3 left-4 bg-[var(--bg1)] px-2 text-xs font-bold text-[var(--ember)] uppercase tracking-widest border border-[var(--stroke)] rounded">Habilidade</div>
                 <h4 className="font-bold text-[var(--text)] mb-2">{activeBackground.ability.name}</h4>
                 <p className="text-sm text-[var(--muted)]">{activeBackground.ability.effect}</p>
              </div>
           </div>
        </div>
      )}

      <FilterModal 
        isOpen={isFilterModalOpen}
        onClose={() => setIsFilterModalOpen(false)}
        options={allTags}
        selectedOptions={selectedTags}
        onApply={setSelectedTags}
      />
    </main>
  );
};

export default JogadorAntecedentes;