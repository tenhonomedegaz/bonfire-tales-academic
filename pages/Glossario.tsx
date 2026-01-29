import React, { useState, useMemo, useEffect, useRef } from 'react';
import { Search, Filter, ArrowUpDown, BookOpen, Loader2, AlertTriangle, X, Hash, ChevronRight, ChevronLeft } from 'lucide-react';
import { GlossaryItem, GlossaryTable } from '../types';

// --- Helpers ---

const normalizeText = (text: string) => {
  if (!text) return "";
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
};

const getDisplayCategory = (categories: string[] = []) => {
  if (categories.includes('Combate')) return 'Combate';
  if (categories.includes('Regras')) return 'Regras';
  if (categories.includes('Dados')) return 'Dados';
  if (categories.includes('Personagem')) return 'Personagem';
  if (categories.length > 0) return categories[0];
  return 'Base';
};

const getCategoryColor = (cat: string) => {
  switch (cat) {
    case 'Combate': return 'text-red-400 border-red-900/50 bg-red-900/10';
    case 'Regras': return 'text-blue-400 border-blue-900/50 bg-blue-900/10';
    case 'Dados': return 'text-purple-400 border-purple-900/50 bg-purple-900/10';
    case 'Personagem': return 'text-green-400 border-green-900/50 bg-green-900/10';
    default: return 'text-[var(--muted)] border-[var(--stroke)] bg-[var(--bg0)]';
  }
};

// --- Components ---

const FilterModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  categories: string[];
  selectedCategories: string[];
  onApply: (cats: string[]) => void;
}> = ({ isOpen, onClose, categories, selectedCategories, onApply }) => {
  const [localSelected, setLocalSelected] = useState<string[]>(selectedCategories);

  useEffect(() => {
    if (isOpen) setLocalSelected(selectedCategories);
  }, [isOpen, selectedCategories]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose} />
      <div className="relative w-full max-w-md bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="p-4 border-b border-[var(--stroke)] flex justify-between items-center bg-[var(--bg2)]">
          <h3 className="font-rpg text-lg font-bold text-[var(--text)] flex items-center gap-2">
            <Filter className="w-4 h-4 text-[var(--ember)]" />
            Filtrar por Categoria
          </h3>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)] transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          <div className="space-y-1">
            {categories.map(cat => {
              const isSelected = localSelected.includes(cat);
              return (
                <label key={cat} className={`flex items-center gap-3 p-3 rounded cursor-pointer transition-colors border ${isSelected ? 'bg-[var(--bg2)] border-[var(--ember)]' : 'bg-[var(--bg0)] border-transparent hover:border-[var(--stroke)]'}`}>
                  <div className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${isSelected ? 'bg-[var(--ember)] border-[var(--ember)]' : 'border-[var(--muted)] bg-[var(--bg1)]'}`}>
                    {isSelected && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                  </div>
                  <input type="checkbox" className="hidden" checked={isSelected} onChange={() => isSelected ? setLocalSelected(prev => prev.filter(c => c !== cat)) : setLocalSelected(prev => [...prev, cat])} />
                  <span className={`text-sm font-medium ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)]'}`}>{cat}</span>
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

const TableRenderer: React.FC<{ table: GlossaryTable }> = ({ table }) => (
  <div className="mt-8">
    {table.title && (
      <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-4 pb-2 border-b border-[var(--stroke)] inline-block">
        {table.title}
      </h3>
    )}
    <div className="overflow-x-auto rounded border border-[var(--stroke)] bg-[var(--bg0)] shadow-sm">
      <table className="w-full text-left text-sm border-collapse">
        <thead className="bg-[var(--bg2)] text-[var(--ember)] uppercase font-bold tracking-wider">
          <tr>
            {table.headers.map((h, i) => (
              <th key={i} className="px-4 py-3 border-b border-[var(--stroke)] first:pl-6 whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--stroke)]">
          {table.rows.map((row, rI) => (
            <tr key={rI} className="hover:bg-[var(--bg1)] transition-colors">
              {row.map((cell, cI) => (
                <td key={cI} className={`px-4 py-3 text-[var(--muted)] first:pl-6 ${cI === 0 ? 'font-medium text-[var(--text)]' : ''}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

// --- Main Page ---

const Glossario: React.FC = () => {
  // Data
  const [data, setData] = useState<GlossaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);

  // Selection
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  // Refs for auto-scroll
  const listRef = useRef<HTMLDivElement>(null);
  const selectedItemRef = useRef<HTMLButtonElement>(null);

  // 1. Fetch
  useEffect(() => {
    fetch('/data/glossary.json')
      .then(res => {
        if (!res.ok) throw new Error(`Erro HTTP: ${res.status}`);
        return res.json();
      })
      .then((jsonData: GlossaryItem[]) => {
        setData(jsonData);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError("Não foi possível carregar o Grimório.");
        setLoading(false);
      });
  }, []);

  // 2. Categories
  const allCategories = useMemo(() => {
    if (data.length === 0) return [];
    const cats = new Set<string>();
    data.forEach(item => item.categories?.forEach(c => cats.add(c)));
    return Array.from(cats).sort();
  }, [data]);

  // 3. Filter & Sort
  const filteredData = useMemo(() => {
    let result = [...data];
    if (searchTerm) {
      const norm = normalizeText(searchTerm);
      result = result.filter(item => 
        normalizeText(item.term).includes(norm) ||
        normalizeText(item.summary).includes(norm) ||
        (item.aliases && item.aliases.some(a => normalizeText(a).includes(norm)))
      );
    }
    if (selectedCategories.length > 0) {
      result = result.filter(item => item.categories?.some(c => selectedCategories.includes(c)));
    }
    result.sort((a, b) => sortOrder === 'asc' 
      ? a.term.localeCompare(b.term, 'pt-BR')
      : b.term.localeCompare(a.term, 'pt-BR')
    );
    return result;
  }, [data, searchTerm, selectedCategories, sortOrder]);

  // 4. Hash Sync & Auto Select
  useEffect(() => {
    if (loading || data.length === 0) return;
    
    // Hash -> State
    const handleHash = () => {
      const hash = window.location.hash.slice(1);
      if (hash && data.some(i => i.slug === hash)) {
        setSelectedSlug(hash);
        // On mobile, if hash changes, open detail
        if (window.innerWidth < 768) setIsMobileDetailOpen(true);
      }
    };
    handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, [loading, data]);

  // Update hash when selection changes
  const handleSelect = (slug: string) => {
    setSelectedSlug(slug);
    window.history.replaceState(null, '', `#${slug}`);
    if (window.innerWidth < 768) setIsMobileDetailOpen(true);
  };

  // Keyboard Nav
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!selectedSlug || isFilterModalOpen) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        const currentIndex = filteredData.findIndex(i => i.slug === selectedSlug);
        let nextIndex = currentIndex;
        
        if (e.key === 'ArrowDown') nextIndex = Math.min(currentIndex + 1, filteredData.length - 1);
        if (e.key === 'ArrowUp') nextIndex = Math.max(currentIndex - 1, 0);
        
        if (nextIndex !== currentIndex) {
          const nextItem = filteredData[nextIndex];
          handleSelect(nextItem.slug);
          // Auto scroll list logic would go here
          document.getElementById(`item-${nextItem.slug}`)?.scrollIntoView({ block: 'nearest' });
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedSlug, filteredData, isFilterModalOpen]);

  // Selected Item Content
  const activeItem = useMemo(() => 
    data.find(i => i.slug === selectedSlug), 
  [data, selectedSlug]);

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)] animate-pulse">Consultando grimório...</p>
    </div>
  );

  if (error) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[50vh] gap-4">
      <AlertTriangle className="w-10 h-10 text-[var(--flame)]" />
      <p className="text-[var(--muted)]">{error}</p>
    </div>
  );

  return (
    <main className="flex flex-col h-[calc(100vh-64px)] bg-[var(--bg0)] overflow-hidden">
      
      {/* --- Toolbar (Sticky Top) --- */}
      <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20">
        <div className="container mx-auto max-w-7xl">
          
          {/* Header Section */}
          <div className="mb-6">
            <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Glossário</h1>
            <p className="text-[var(--muted)] text-sm">
              Busque termos, regras e sinônimos do sistema.
            </p>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            {/* Search */}
            <div className="relative flex-grow">
              <input 
                type="text" 
                placeholder="Buscar termo..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[var(--bg0)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none"
              />
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
            </div>
            
            {/* Actions */}
            <div className="flex gap-2 shrink-0">
               <button onClick={() => setIsFilterModalOpen(true)} className={`flex items-center gap-2 px-3 py-2 rounded border text-sm font-medium transition-colors ${selectedCategories.length > 0 ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)]' : 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)]'}`}>
                 <Filter className="w-4 h-4" />
                 <span className="hidden sm:inline">Filtros</span>
                 {selectedCategories.length > 0 && <span className="bg-[var(--ember)] text-white text-[10px] w-4 h-4 rounded-full flex items-center justify-center">{selectedCategories.length}</span>}
               </button>
               <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg0)] border border-[var(--stroke)] rounded text-[var(--muted)] hover:text-[var(--text)] transition-colors text-sm font-medium">
                 <ArrowUpDown className="w-4 h-4" />
                 <span className="hidden sm:inline">{sortOrder === 'asc' ? 'A-Z' : 'Z-A'}</span>
               </button>
            </div>
          </div>
          
          {/* Filter Tags */}
          {selectedCategories.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {selectedCategories.map(cat => (
                <button key={cat} onClick={() => setSelectedCategories(prev => prev.filter(c => c !== cat))} className="flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[var(--bg2)] border border-[var(--ember)] text-[var(--muted)] hover:text-white group">
                  {cat} <span className="group-hover:text-[var(--flame)] font-bold">×</span>
                </button>
              ))}
              <button onClick={() => setSelectedCategories([])} className="text-xs text-[var(--muted)] hover:text-[var(--text)] underline px-2">Limpar</button>
            </div>
          )}
        </div>
      </div>

      {/* --- Master Detail Grid --- */}
      <div className="flex-1 flex overflow-hidden container mx-auto max-w-7xl md:px-4">
        
        {/* Left Col: List */}
        <div className="w-full md:w-80 lg:w-96 flex-shrink-0 flex flex-col border-r border-[var(--stroke)] bg-[var(--bg0)] md:bg-[var(--bg1)]/50">
           
           <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1" ref={listRef}>
             {filteredData.length > 0 ? (
               filteredData.map(item => {
                 const isSelected = selectedSlug === item.slug;
                 const tag = getDisplayCategory(item.categories);
                 const tagColor = getCategoryColor(tag);

                 return (
                   <button
                     key={item.slug}
                     id={`item-${item.slug}`}
                     onClick={() => handleSelect(item.slug)}
                     className={`w-full text-left px-3 py-2.5 rounded border transition-all duration-200 group flex items-center justify-between gap-3 ${
                       isSelected 
                         ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                         : 'bg-transparent border-transparent hover:bg-[var(--bg1)] hover:border-[var(--stroke)]'
                     }`}
                   >
                     <span className={`text-sm font-medium truncate ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                       {item.term}
                     </span>
                     <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${tagColor} whitespace-nowrap`}>
                       {tag}
                     </span>
                   </button>
                 );
               })
             ) : (
               <div className="text-center py-10 text-[var(--muted)] text-sm px-4">
                 Nenhum termo encontrado.
               </div>
             )}
           </div>
        </div>

        {/* Right Col: Detail (Desktop) */}
        <div className="hidden md:flex flex-1 flex-col bg-[var(--bg0)] relative overflow-hidden">
           {activeItem ? (
             <div className="absolute inset-0 overflow-y-auto custom-scrollbar p-8 lg:p-12 animate-in fade-in duration-300">
                {/* Header */}
                <div className="mb-8 border-b border-[var(--stroke)] pb-6">
                  <div className="flex items-center gap-3 mb-4">
                     <BookOpen className="w-6 h-6 text-[var(--ember)]" />
                     <div className="flex gap-2">
                       {activeItem.categories?.map(cat => (
                         <span key={cat} className={`text-xs font-bold uppercase tracking-wider px-2 py-1 rounded border ${getCategoryColor(cat)}`}>
                           {cat}
                         </span>
                       ))}
                     </div>
                  </div>
                  <h1 className="font-rpg text-4xl font-bold text-[var(--text)] mb-2">{activeItem.term}</h1>
                  <p className="text-lg text-[var(--muted)] italic">{activeItem.summary}</p>
                </div>

                {/* Body */}
                <div 
                  className="prose prose-invert max-w-none prose-p:text-[var(--text)] prose-headings:text-[var(--text)] prose-strong:text-[var(--ember)] prose-a:text-[var(--flame)] prose-code:text-[var(--spark)] prose-code:bg-[var(--bg2)] prose-code:px-1 prose-code:rounded prose-code:border prose-code:border-[var(--stroke)] leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: activeItem.body }} 
                />

                {/* Table Render */}
                {activeItem.table && <TableRenderer table={activeItem.table} />}

                {/* Aliases Footer */}
                {activeItem.aliases && activeItem.aliases.length > 0 && (
                  <div className="mt-12 pt-6 border-t border-[var(--stroke)] text-sm text-[var(--muted)]">
                    <span className="font-bold text-[var(--ember)]">Conhecido como: </span>
                    {activeItem.aliases.join(', ')}
                  </div>
                )}
             </div>
           ) : (
             <div className="flex flex-col items-center justify-center h-full text-[var(--muted)] opacity-50 p-8 text-center">
               <div className="w-20 h-20 rounded-full border-2 border-dashed border-[var(--stroke)] flex items-center justify-center mb-4">
                 <ChevronLeft className="w-8 h-8" />
               </div>
               <p className="text-lg font-rpg">Selecione um termo no grimório para ler os detalhes.</p>
             </div>
           )}
        </div>

      </div>

      {/* --- Mobile Detail Drawer --- */}
      {isMobileDetailOpen && activeItem && (
        <div className="fixed inset-0 z-50 md:hidden bg-[var(--bg0)] flex flex-col animate-in slide-in-from-bottom duration-300">
           {/* Mobile Header */}
           <div className="flex items-center justify-between p-4 border-b border-[var(--stroke)] bg-[var(--bg1)]">
             <button 
               onClick={() => setIsMobileDetailOpen(false)}
               className="flex items-center gap-2 text-[var(--muted)] hover:text-[var(--text)]"
             >
               <ChevronLeft className="w-5 h-5" />
               <span className="font-bold uppercase text-xs tracking-wider">Voltar</span>
             </button>
             <div className="flex gap-2">
               <button className="p-2" onClick={() => handleSelect(filteredData[Math.max(0, filteredData.findIndex(i => i.slug === selectedSlug) - 1)].slug)}>
                  <ChevronLeft className="w-5 h-5 text-[var(--text)]" />
               </button>
               <button className="p-2" onClick={() => handleSelect(filteredData[Math.min(filteredData.length - 1, filteredData.findIndex(i => i.slug === selectedSlug) + 1)].slug)}>
                  <ChevronRight className="w-5 h-5 text-[var(--text)]" />
               </button>
             </div>
           </div>

           {/* Mobile Content */}
           <div className="flex-1 overflow-y-auto p-6">
              <div className="mb-6">
                 <div className="flex flex-wrap gap-2 mb-3">
                   {activeItem.categories?.map(cat => (
                     <span key={cat} className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getCategoryColor(cat)}`}>
                       {cat}
                     </span>
                   ))}
                 </div>
                 <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-2">{activeItem.term}</h2>
                 <p className="text-sm text-[var(--muted)] italic border-l-2 border-[var(--ember)] pl-3">
                   {activeItem.summary}
                 </p>
              </div>
              <div 
                  className="prose prose-invert prose-sm max-w-none prose-p:text-[var(--text)] prose-strong:text-[var(--ember)] prose-code:text-[var(--spark)]"
                  dangerouslySetInnerHTML={{ __html: activeItem.body }} 
              />
              {/* Table Render Mobile */}
              {activeItem.table && <TableRenderer table={activeItem.table} />}
           </div>
        </div>
      )}

      <FilterModal 
        isOpen={isFilterModalOpen}
        onClose={() => setIsFilterModalOpen(false)}
        categories={allCategories}
        selectedCategories={selectedCategories}
        onApply={setSelectedCategories}
      />
    </main>
  );
};

export default Glossario;