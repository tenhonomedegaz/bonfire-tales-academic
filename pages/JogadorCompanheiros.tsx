import React, { useState, useMemo } from 'react';
import { Search, Filter, ArrowUpDown, Hammer, ChevronRight, BookOpen } from 'lucide-react';

interface PlaceholderItem {
  slug: string;
  name: string;
  description: string;
  environment: string;
}

const placeholderData: PlaceholderItem[] = [
    { slug: 'lobo', name: 'Companheiro: Lobo', description: 'Um predador de matilha, leal e com um uivo intimidador.', environment: 'Floresta' },
    { slug: 'urso', name: 'Companheiro: Urso', description: 'Uma força da natureza, com garras poderosas e grande resistência.', environment: 'Montanha' },
    { slug: 'pantera', name: 'Companheiro: Pantera', description: 'Uma caçadora furtiva das selvas, mestre da emboscada.', environment: 'Selva' },
    { slug: 'aguia', name: 'Companheiro: Águia Gigante', description: 'Um aliado aéreo com visão aguçada e garras afiadas.', environment: 'Aéreo' },
    { slug: 'javali', name: 'Companheiro: Javali Atroz', description: 'Uma besta teimosa e feroz, que ataca sem hesitação.', environment: 'Floresta' },
];

const title = "Companheiros";
const subtitle = "Bestas leais que lutam ao lado de seus mestres.";

const JogadorCompanheiros: React.FC = () => {
    const [searchTerm, setSearchTerm] = useState('');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

    const filteredData = useMemo(() => {
        let result = [...placeholderData];
        if (searchTerm) {
            result = result.filter(item => item.name.toLowerCase().includes(searchTerm.toLowerCase()));
        }
        result.sort((a, b) => sortOrder === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
        return result;
    }, [searchTerm, sortOrder]);

    const activeItem = useMemo(() => placeholderData.find(item => item.slug === selectedSlug), [selectedSlug]);
    
    return (
        <main className="flex flex-col h-[calc(100vh-64px)] bg-[var(--bg0)] overflow-hidden">
            {/* Toolbar */}
            <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20">
              <div className="container mx-auto max-w-7xl">
                <div className="mb-4">
                  <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">{title}</h1>
                  <p className="text-[var(--muted)] text-sm">{subtitle}</p>
                </div>
                <div className="flex flex-col md:flex-row gap-3">
                    <div className="relative flex-grow">
                        <input 
                            type="text" 
                            placeholder="Buscar companheiro..." 
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[var(--bg0)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none"
                        />
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <button className="flex items-center gap-2 px-3 py-2 rounded border text-sm font-medium bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] opacity-50 cursor-not-allowed">
                            <Filter className="w-4 h-4" /> Filtros
                        </button>
                        <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg0)] border border-[var(--stroke)] rounded text-[var(--muted)] hover:text-[var(--text)] transition-colors text-sm font-medium">
                            <ArrowUpDown className="w-4 h-4" /> {sortOrder === 'asc' ? 'A-Z' : 'Z-A'}
                        </button>
                    </div>
                </div>
              </div>
            </div>
            
            {/* Main Content Grid */}
            <div className="flex-1 flex overflow-hidden container mx-auto max-w-7xl md:px-4">
                {/* Left List */}
                <div className="w-full md:w-1/3 lg:w-80 flex-shrink-0 flex flex-col border-r border-[var(--stroke)] bg-[var(--bg0)] md:bg-[var(--bg1)]/30">
                    <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                        {filteredData.map(item => {
                            const isSelected = selectedSlug === item.slug;
                            return (
                                <button
                                    key={item.slug}
                                    onClick={() => setSelectedSlug(item.slug)}
                                    className={`w-full text-left px-3 py-3 rounded border transition-all duration-200 group flex justify-between items-center ${
                                        isSelected 
                                        ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                                        : 'bg-transparent border-transparent hover:bg-[var(--bg1)] hover:border-[var(--stroke)]'
                                    }`}
                                >
                                    <span className={`text-sm font-bold ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>{item.name}</span>
                                    {isSelected && <ChevronRight className="w-4 h-4 text-[var(--ember)]" />}
                                </button>
                            );
                        })}
                    </div>
                </div>
                {/* Right Detail */}
                <div className="hidden md:flex flex-1 flex-col bg-[var(--bg0)] relative overflow-y-auto custom-scrollbar p-6 md:p-10">
                    {activeItem ? (
                        <div className="animate-in fade-in duration-300">
                            <h2 className="font-rpg text-4xl font-bold text-[var(--text)] mb-2">{activeItem.name}</h2>
                            <p className="text-lg text-[var(--muted)] italic mb-8 border-b border-[var(--stroke)] pb-6">{activeItem.description}</p>
                            
                            <div className="p-6 rounded-lg bg-[var(--bg1)] border-l-4 border-[var(--ember)] flex items-start gap-4 shadow-lg">
                                <Hammer className="w-8 h-8 text-[var(--ember)] shrink-0 mt-1" />
                                <div>
                                    <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-2">Conteúdo em Construção</h3>
                                    <p className="text-[var(--muted)]">As estatísticas e habilidades completas para este companheiro ainda estão sendo catalogadas. Volte em breve para mais informações.</p>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-[var(--muted)] opacity-50 p-8 text-center">
                            <BookOpen className="w-16 h-16 mb-4" />
                            <p className="text-lg font-rpg">Selecione um companheiro na lista para ver os detalhes.</p>
                        </div>
                    )}
                </div>
            </div>
        </main>
    );
};

export default JogadorCompanheiros;
