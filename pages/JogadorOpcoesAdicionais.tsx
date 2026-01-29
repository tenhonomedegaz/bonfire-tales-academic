
import React, { useState, useEffect, useMemo } from 'react';
import { Search, SlidersHorizontal, ArrowUpDown, X, Check, Loader2, AlertTriangle, BookOpen, ChevronRight, Dna, Info, Sparkles, Shield, Swords } from 'lucide-react';
import { GameOption } from '../types';

// --- HELPERS ---

const getTypeTagStyle = (type: GameOption['type']) => {
    switch (type) {
        case 'Estilo de Luta':
            return 'bg-red-900/50 text-red-300 border-red-700/50';
        case 'Manobra de Combate':
            return 'bg-orange-900/50 text-orange-300 border-orange-700/50';
        case 'Invocação Mística':
            return 'bg-purple-900/50 text-purple-300 border-purple-700/50';
        case 'Estilo de Ki':
            return 'bg-cyan-900/50 text-cyan-300 border-cyan-700/50';
        case 'Infusão':
            return 'bg-blue-900/50 text-blue-300 border-blue-700/50';
        default:
            return 'bg-[var(--bg0)] text-[var(--muted)] border-[var(--stroke)]';
    }
};

const getPrerequisiteString = (option: GameOption): string => {
    const parts = [`Nível ${option.level}`];
    
    // Skill
    if (option.prerequisites.skills.length > 0) {
        parts.push(`Prof. em ${option.prerequisites.skills[0]}`);
    } 
    // Ability (All)
    else if (option.prerequisites.abilitiesAll.length > 0) {
        const prereq = option.prerequisites.abilitiesAll[0];
        parts.push(`${prereq.ability.substring(0, 3)} ${prereq.min}+`);
    } 
    // Ability (Any)
    else if (option.prerequisites.abilitiesAny.length > 0) {
        const prereqGroup = option.prerequisites.abilitiesAny[0];
        if (prereqGroup.options.length > 0) {
            const prereq = prereqGroup.options[0];
            let text = `${prereq.ability.substring(0, 3)} ${prereq.min}+`;
            if (prereqGroup.options.length > 1) {
              text += ` ou...`;
            }
            parts.push(text);
        }
    }

    return parts.join(' - ');
};


// --- DATA ---

const CATEGORY_DESCRIPTIONS: Record<string, { title: string; text: string; icon: React.ReactNode }> = {
  "Estilo de Luta": {
    title: "O que é um Estilo de Luta?",
    text: "Técnicas permanentes que definem sua forma de lutar. Você escolhe 1 quando ganhar acesso e seus benefícios ficam ativos sempre que cumprir as condições.",
    icon: <Swords className="w-6 h-6" />
  },
  "Manobra de Combate": {
    title: "O que é uma Manobra de Combate?",
    text: "Táticas especiais usadas em combate. Normalmente gastam Dados de Combate (ou recurso equivalente) e adicionam controle, dano ou utilidade em ataques.",
    icon: <Swords className="w-6 h-6" />
  },
  "Invocação Mística": {
    title: "O que é uma Invocação Mística?",
    text: "Poderes do Bruxo escolhidos como aprimoramentos. Algumas exigem nível, pacto ou magias específicas.",
    icon: <Sparkles className="w-6 h-6" />
  },
  "Estilo de Ki": {
    title: "O que é um Estilo de Ki?",
    text: "Variações do fluxo de Ki do Monge. Melhoram mobilidade, defesa ou técnicas e costumam interagir com recursos de Ki.",
    icon: <Sparkles className="w-6 h-6" />
  },
  "Infusão": {
    title: "O que é uma Infusão?",
    text: "Protótipos arcanotecnológicos do Artífice que alteram itens. Podem exigir nível e geralmente interagem com limites de itens infundidos.",
    icon: <Sparkles className="w-6 h-6" />
  },
  fallback: {
    title: "O que é esta Opção?",
    text: "Esta é uma opção adicional ligada ao sistema. Consulte o mestre se tiver dúvidas sobre seu funcionamento.",
    icon: <Info className="w-6 h-6" />
  }
};

// --- TYPES ---
interface GameOptionFilters {
    level: number;
    classes: string[];
    abilities: string[];
    skills: string[];
}

type DetailViewMode = 'option' | 'category';

// --- CHILD COMPONENTS ---

const Chip: React.FC<{ text: string, onClick?: () => void, icon?: React.ReactNode, className?: string, title?: string }> = ({ text, onClick, icon, className = "", title }) => {
  const baseClasses = "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border transition-colors";
  const interactiveClasses = onClick ? "cursor-pointer hover:bg-[var(--bg2)]" : "";
  
  return (
    <button onClick={onClick} disabled={!onClick} className={`${baseClasses} ${interactiveClasses} ${className}`} title={title}>
      {icon}
      <span className="truncate">{text}</span>
    </button>
  );
};

const CategoryInfoView: React.FC<{ type: GameOption['type']; onBack: () => void }> = ({ type, onBack }) => {
  const info = CATEGORY_DESCRIPTIONS[type] || CATEGORY_DESCRIPTIONS.fallback;

  return (
    <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg p-8 animate-in fade-in duration-300 shadow-xl flex flex-col gap-6">
      <div className="flex items-center gap-3 text-[var(--ember)]">
        {info.icon}
        <h2 className="font-rpg text-2xl font-bold">{info.title}</h2>
      </div>
      <p className="text-[var(--muted)] leading-relaxed">{info.text}</p>
      <button onClick={onBack} className="mt-4 self-start px-6 py-2 bg-[var(--ember)] hover:bg-[var(--flame)] text-white font-bold rounded text-sm transition-colors">
        Voltar para a Opção
      </button>
    </div>
  );
};

const OptionDetailView: React.FC<{ option: GameOption; onCategoryClick: () => void }> = ({ option, onCategoryClick }) => (
  <div className="animate-in fade-in duration-300">
    <div className="pb-6 mb-8 border-b border-[var(--stroke)]">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Chip text={option.type} onClick={onCategoryClick} className="bg-[var(--bg2)] border-[var(--ember)] text-[var(--ember)] hover:border-[var(--flame)]" title="Clique para saber mais sobre esta categoria" />
        {option.classes.map(c => <Chip key={c} text={c} className="bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)]" />)}
        <Chip text={`Nível ${option.level}`} className="bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)]" />
      </div>
      <h2 className="font-rpg text-4xl font-bold text-[var(--text)]">{option.name}</h2>
      <p className="text-lg text-[var(--muted)] italic mt-2">{option.description}</p>
    </div>
    
    <div className="space-y-6">
      <div className="p-6 rounded-lg bg-[var(--bg1)] border-l-4 border-[var(--ember)] shadow-lg">
        <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-3 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-[var(--ember)]" />
          Efeito Mecânico
        </h3>
        <p className="text-[var(--text)] leading-relaxed whitespace-pre-wrap">{option.effect}</p>
      </div>

      <div className="p-6 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)]">
        <h3 className="font-rpg text-lg font-bold text-[var(--text)] mb-4 flex items-center gap-2">
            <Dna className="w-4 h-4 text-[var(--muted)]" /> Pré-Requisitos
        </h3>
        <div className="space-y-3 text-sm text-[var(--muted)]">
            <p><strong className="text-[var(--text)] min-w-[150px] inline-block">Nível Mínimo:</strong> {option.level}</p>
            <p><strong className="text-[var(--text)] min-w-[150px] inline-block">Classes:</strong> {option.classes.join(', ')}</p>
            {option.prerequisites.abilitiesAll.length > 0 && 
                <p><strong className="text-[var(--text)] min-w-[150px] inline-block">Atributos (TODOS):</strong> {option.prerequisites.abilitiesAll.map(a => `${a.ability} ${a.min}`).join(', ')}</p>}
            {option.prerequisites.abilitiesAny.map(group =>
                <p key={group.group}><strong className="text-[var(--text)] min-w-[150px] inline-block">Atributos (QUALQUER):</strong> {group.options.map(o => `${o.ability} ${o.min}`).join(' ou ')}</p>)}
            {option.prerequisites.skills.length > 0 && 
                <p><strong className="text-[var(--text)] min-w-[150px] inline-block">Perícias:</strong> {option.prerequisites.skills.join(', ')}</p>}
            {option.prerequisites.abilitiesAll.length === 0 && option.prerequisites.abilitiesAny.length === 0 && option.prerequisites.skills.length === 0 &&
                <p className="opacity-70">Nenhum pré-requisito adicional.</p>
            }
        </div>
      </div>
    </div>
  </div>
);

// --- MAIN PAGE ---

const JogadorOpcoesAdicionais: React.FC = () => {
    const [optionsData, setOptionsData] = useState<GameOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // State
    const [searchTerm, setSearchTerm] = useState('');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
    const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
    const [detailViewMode, setDetailViewMode] = useState<DetailViewMode>('option');

    // Filters
    const [filters, setFilters] = useState<GameOptionFilters>({
        level: 20, classes: [], abilities: [], skills: []
    });

    // Fetch data
    useEffect(() => {
        fetch('/data/options.json')
            .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP error: ${res.status}`)))
            .then((data: GameOption[]) => {
                setOptionsData(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch options:", err);
                setError("Não foi possível carregar as opções.");
                setLoading(false);
            });
    }, []);

    const filterOptions = useMemo(() => {
        const classes = new Set<string>();
        const skills = new Set<string>();
        const abilities = new Set<string>();
        optionsData.forEach(opt => {
            opt.classes.forEach(c => classes.add(c));
            opt.prerequisites.skills.forEach(s => skills.add(s));
            opt.prerequisites.abilitiesAll.forEach(a => abilities.add(a.ability));
            opt.prerequisites.abilitiesAny.forEach(g => g.options.forEach(a => abilities.add(a.ability)));
        });
        return {
            classes: Array.from(classes).sort(),
            skills: Array.from(skills).sort(),
            abilities: Array.from(abilities).sort()
        };
    }, [optionsData]);

    const filteredData = useMemo(() => {
        let result = [...optionsData];
        if (searchTerm) {
            const q = searchTerm.toLowerCase();
            result = result.filter(opt => opt.name.toLowerCase().includes(q) || opt.tags.some(t => t.toLowerCase().includes(q)));
        }
        result = result.filter(opt => {
            if (opt.level > filters.level) return false;
            if (filters.classes.length > 0 && !filters.classes.some(c => opt.classes.includes(c))) return false;
            if (filters.abilities.length > 0) {
                const reqAbilities = new Set([...opt.prerequisites.abilitiesAll.map(a => a.ability), ...opt.prerequisites.abilitiesAny.flatMap(g => g.options.map(a => a.ability))]);
                if (!filters.abilities.some(a => reqAbilities.has(a))) return false;
            }
            if (filters.skills.length > 0 && !filters.skills.some(s => opt.prerequisites.skills.includes(s))) return false;
            return true;
        });
        result.sort((a, b) => sortOrder === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
        return result;
    }, [optionsData, searchTerm, filters, sortOrder]);

    const activeItem = useMemo(() => optionsData.find(opt => opt.slug === selectedSlug), [optionsData, selectedSlug]);
    const activeFilterCount = filters.classes.length + filters.abilities.length + filters.skills.length + (filters.level < 20 ? 1 : 0);

    const handleSelectOption = (slug: string) => {
      setSelectedSlug(slug);
      setDetailViewMode('option');
    };

    if (loading) return <div className="flex-1 flex items-center justify-center"><Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" /></div>;
    if (error) return <div className="flex-1 flex items-center justify-center text-center"><AlertTriangle className="w-10 h-10 text-[var(--flame)] mb-4" /><p>{error}</p></div>;

    return (
        <main className="bg-[var(--bg0)]">
            {/* Toolbar */}
            <div className="sticky top-16 md:top-0 z-40 bg-[var(--bg1)]/95 backdrop-blur-md border-b border-[var(--stroke)] p-4">
              <div className="container mx-auto max-w-7xl">
                <div className="mb-4">
                  <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Opções Adicionais</h1>
                  <p className="text-[var(--muted)] text-sm">Estilos de Luta, Manobras, Invocações e mais.</p>
                </div>
                <div className="flex flex-col md:flex-row gap-3">
                    <div className="relative flex-grow">
                        <input type="text" placeholder="Buscar opção por nome, tag..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[var(--bg0)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none" />
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <button onClick={() => setIsFilterModalOpen(true)} className={`flex items-center gap-2 px-3 py-2 rounded border text-sm font-medium transition-colors ${activeFilterCount > 0 ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)]' : 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)]'}`}>
                            <SlidersHorizontal className="w-4 h-4" /> Filtros
                            {activeFilterCount > 0 && <span className="bg-[var(--ember)] text-white text-[10px] w-5 h-5 rounded-full flex items-center justify-center">{activeFilterCount}</span>}
                        </button>
                        <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg0)] border border-[var(--stroke)] rounded text-[var(--muted)] hover:text-[var(--text)] transition-colors text-sm font-medium">
                            <ArrowUpDown className="w-4 h-4" /> {sortOrder === 'asc' ? 'A-Z' : 'Z-A'}
                        </button>
                    </div>
                </div>
              </div>
            </div>
            
            {/* Main Content Grid */}
            <div className="container mx-auto max-w-7xl px-4 py-8">
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-[384px_1fr] gap-8">
                
                {/* Left List */}
                <div className="md:col-span-1 flex flex-col gap-2">
                    {filteredData.length > 0 ? filteredData.map(item => {
                        const isSelected = selectedSlug === item.slug;
                        return (
                            <button
                                key={item.slug}
                                onClick={() => handleSelectOption(item.slug)}
                                className={`w-full text-left p-4 rounded border transition-all duration-200 group flex justify-between items-center gap-4 ${
                                    isSelected ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_4px_0_0_var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] hover:border-[var(--muted)]'
                                }`}
                            >
                                <div className="flex flex-col gap-2 flex-grow min-w-0">
                                    <div className="flex justify-between items-start gap-2">
                                        <span className={`font-bold truncate ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                                            {item.name}
                                        </span>
                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border whitespace-nowrap ${getTypeTagStyle(item.type)}`}>
                                            {item.type}
                                        </span>
                                    </div>
                                    <div className="text-xs text-gray-500 font-mono">
                                        {getPrerequisiteString(item)}
                                    </div>
                                </div>
                                {isSelected && <ChevronRight className="w-5 h-5 text-[var(--ember)] shrink-0" />}
                            </button>
                        );
                    }) : (
                        <div className="text-center p-8 text-sm text-[var(--muted)] bg-[var(--bg1)] rounded border border-dashed border-[var(--stroke)]">Nenhuma opção encontrada.</div>
                    )}
                </div>

                {/* Right Detail */}
                <div className="md:col-span-2 lg:col-span-1">
                    {activeItem ? (
                      detailViewMode === 'category' ? (
                        <CategoryInfoView type={activeItem.type} onBack={() => setDetailViewMode('option')} />
                      ) : (
                        <OptionDetailView option={activeItem} onCategoryClick={() => setDetailViewMode('category')} />
                      )
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-[var(--muted)] opacity-50 p-8 text-center bg-[var(--bg1)] rounded border border-dashed border-[var(--stroke)]">
                            <BookOpen className="w-16 h-16 mb-4" />
                            <p className="text-lg font-rpg">Selecione uma opção para ver os detalhes.</p>
                        </div>
                    )}
                </div>
              </div>
            </div>
            
            <FilterModal isOpen={isFilterModalOpen} onClose={() => setIsFilterModalOpen(false)} currentFilters={filters} onApplyFilters={setFilters} options={filterOptions} />
        </main>
    );
};

const FilterModal: React.FC<{
    isOpen: boolean;
    onClose: () => void;
    currentFilters: GameOptionFilters;
    onApplyFilters: (filters: GameOptionFilters) => void;
    options: { classes: string[], skills: string[], abilities: string[] };
}> = ({ isOpen, onClose, currentFilters, onApplyFilters, options }) => {
    const [localFilters, setLocalFilters] = useState(currentFilters);
    useEffect(() => { if (isOpen) setLocalFilters(currentFilters); }, [isOpen, currentFilters]);
    if (!isOpen) return null;

    const toggleFilter = (type: 'classes' | 'abilities' | 'skills', value: string) => {
        setLocalFilters(prev => ({ ...prev, [type]: prev[type].includes(value) ? prev[type].filter(i => i !== value) : [...prev[type], value] }));
    };
    const apply = () => { onApplyFilters(localFilters); onClose(); };
    const clearAll = () => setLocalFilters({ level: 20, classes: [], abilities: [], skills: [] });

    const FilterSection = ({ title, type, items }: { title: string, type: 'classes' | 'abilities' | 'skills', items: string[] }) => (
        <div className="mb-4">
            <h4 className="text-xs font-bold uppercase text-[var(--muted)] tracking-widest mb-2 border-b border-[var(--stroke)] pb-1">{title}</h4>
            <div className="flex flex-wrap gap-2">
                {items.map(item => {
                    const isSelected = localFilters[type].includes(item);
                    return (
                        <button key={item} onClick={() => toggleFilter(type, item)}
                            className={`px-3 py-1.5 rounded text-xs font-bold border flex items-center gap-2 transition-colors ${isSelected ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)]' : 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] hover:border-[var(--muted)]'}`}>
                            {item} {isSelected && <Check className="w-3 h-3 text-[var(--ember)]" />}
                        </button>
                    );
                })}
            </div>
        </div>
    );

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
            <div className="relative w-full max-w-2xl bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg shadow-2xl flex flex-col max-h-[85vh]">
                <div className="p-4 border-b border-[var(--stroke)] flex justify-between items-center bg-[var(--bg2)]">
                    <h3 className="font-rpg text-lg font-bold text-[var(--text)]">Filtros</h3>
                    <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)]"><X className="w-5 h-5" /></button>
                </div>
                <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-6">
                    <div>
                        <label className="text-xs font-bold uppercase text-[var(--muted)] tracking-widest mb-2 block">Nível Máximo: <span className="text-[var(--ember)] font-mono">{localFilters.level}</span></label>
                        <input type="range" min="1" max="20" value={localFilters.level} onChange={(e) => setLocalFilters(f => ({ ...f, level: parseInt(e.target.value) }))}
                            className="w-full h-2 bg-[var(--bg0)] rounded-lg appearance-none cursor-pointer accent-[var(--ember)]" />
                    </div>
                    <FilterSection title="Classes" type="classes" items={options.classes} />
                    <FilterSection title="Requisito de Atributo" type="abilities" items={options.abilities} />
                    <FilterSection title="Requisito de Perícia" type="skills" items={options.skills} />
                </div>
                <div className="p-4 border-t border-[var(--stroke)] bg-[var(--bg2)] flex gap-3 justify-end">
                    <button onClick={clearAll} className="px-4 py-2 border border-[var(--stroke)] bg-[var(--bg1)] text-[var(--muted)] hover:text-[var(--text)] font-bold rounded text-sm">Limpar</button>
                    <button onClick={apply} className="px-6 py-2 bg-[var(--ember)] hover:bg-[var(--flame)] text-white font-bold rounded text-sm">Aplicar</button>
                </div>
            </div>
        </div>
    );
};

export default JogadorOpcoesAdicionais;
