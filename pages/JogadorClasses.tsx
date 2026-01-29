import React, { useState, useEffect, useMemo } from 'react';
import { 
  Sword, 
  Shield, 
  Layers, 
  Search, 
  Loader2, 
  AlertTriangle, 
  Check,
  ChevronDown,
  Hammer,
  Link as LinkIcon,
  Scroll,
  Info
} from 'lucide-react';
import { useLocation, useNavigate, Link } from 'react-router-dom';

// --- Types ---

interface CoreTrait {
  label: string;
  value: string;
}

interface Multiclassing {
  requirements: string;
  skillProficiencies: string;
  toolProficiencies: string;
  armorTraining: string;
}

interface LinkItem {
  label: string;
  href: string;
  kind: 'spell' | 'item' | 'rule';
}

interface FeatureTable {
  title: string;
  columns: string[];
  rows: (string | number)[][];
}

interface Feature {
  level: number;
  title: string;
  sourceTag?: string; // Legacy, ignored in UI
  text?: string;
  body?: string;
  type: 'class' | 'subclass';
  subclassSlug?: string;
  subclassName?: string;
  tables?: FeatureTable[];
  links?: LinkItem[];
}

interface PatchGroupHeader {
  label: string;
  span: number;
}

interface SubclassTablePatch {
  mode: 'addColumns';
  insertAfter: string;
  groupHeader?: PatchGroupHeader;
  extraColumns: string[]; 
  rowsByLevel: Record<string, (string | number)[]>;
}

interface Subclass {
  name: string;
  slug: string;
  tagline: string;
  features: Feature[];
  tablePatch?: SubclassTablePatch;
}

interface ClassTableBase {
  columns: string[];
  rows: (string | number)[][];
}

interface ClassData {
  name: string;
  slug: string;
  tagline: string;
  coreTraits: CoreTrait[];
  multiclassing?: Multiclassing;
  classTable: {
    base: ClassTableBase;
  };
  features: Feature[];
  subclasses: Subclass[];
}

// --- Helpers ---

const parseMarkdown = (text: string) => {
  if (!text) return "";
  let html = text
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong class="text-[var(--ember)]"><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--text)]">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="text-[var(--muted)]">$1</em>')
    .replace(/\n\n/g, '<div class="h-2"></div>')
    .replace(/\n/g, '<br/>')
    .replace(/^\* (.*$)/gim, '<li class="ml-4 list-disc marker:text-[var(--ember)]">$1</li>');
  return html;
};

// Helper to format header labels with forced stacking for compactness
const formatHeader = (text: string) => {
  if (!text) return <span></span>;

  const lower = text.toLowerCase();

  // Helper builder for stacked text
  const stackWords = (top: string, bottom: string) => (
    <div className="flex flex-col items-center justify-end h-full leading-tight w-full">
      <span>{top}</span>
      <span className="text-[9px] opacity-80 whitespace-nowrap">{bottom}</span>
    </div>
  );

  // Specific mappings for compact headers based on user request
  if (lower.includes("retomar") && lower.includes("fôlego")) return stackWords("Retomar", "Fôlego");
  if (lower.includes("maestrias") || (lower.includes("maestria") && lower.includes("arma"))) return stackWords("Maestrias", "de Armas");
  if (lower.includes("manobras") && lower.includes("conhecidas")) return stackWords("Manobras", "Conhecidas");
  if (lower.includes("dados") && lower.includes("combate")) return stackWords("Dados", "de Combate");
  if (lower.includes("quantidade") && lower.includes("dados")) return stackWords("Quantidade", "de Dados");
  
  // Other common long headers
  if (lower.includes("infusões") && lower.includes("conhecidas")) return stackWords("Infusões", "Conhecidas");
  if (lower.includes("itens") && lower.includes("infundidos")) return stackWords("Itens", "Infundidos");
  if (lower.includes("deslocamento") && lower.includes("armadura")) return stackWords("Desloc.", "S/ Armadura");
  if (lower.includes("artes") && lower.includes("marciais")) return stackWords("Artes", "Marciais");
  if (lower.includes("ataque") && lower.includes("furtivo")) return stackWords("Ataque", "Furtivo");
  if (lower.includes("pontos") && lower.includes("ki")) return stackWords("Pontos", "de Ki");
  if (lower.includes("pontos") && lower.includes("feitiçaria")) return stackWords("Pontos", "Feitiçaria");
  if (lower.includes("magias") && lower.includes("conhecidas")) return stackWords("Magias", "Conhecidas");
  if (lower.includes("magias") && lower.includes("preparadas")) return stackWords("Magias", "Preparadas");

  return <span>{text}</span>;
};

// --- Table Column Widths (Responsive Strategy) ---
const getColumnStyle = (header: string) => {
  const h = (header || '').toLowerCase();
  
  // The Big Feature Column (Flexible)
  if (h.includes('habilidades') || h.includes('features') || h.includes('características')) {
    return { minWidth: '180px', width: 'auto', textAlign: 'left' as const, isFeature: true };
  }

  // Nível / Level
  if (h === 'nível' || h === 'level' || h === 'nvl') return { minWidth: '40px', width: '40px', textAlign: 'center' as const, isFeature: false };
  
  // PB
  if (h === 'pb' || h.includes('prof')) return { minWidth: '35px', width: '35px', textAlign: 'center' as const, isFeature: false };
  
  // Spell Slots / Numeric Counters (Short headers)
  if (/^\d+(st|nd|rd|th|º|ª)$/.test(h)) return { minWidth: '30px', width: '30px', textAlign: 'center' as const, isFeature: false };
  
  // Medium Headers
  if (h === 'truques' || h === 'cantrips') return { minWidth: '55px', textAlign: 'center' as const, isFeature: false };
  if (h === 'magias' || h === 'spells') return { minWidth: '55px', textAlign: 'center' as const, isFeature: false };
  
  // Long Headers - Optimized for Stacked View (Reduced Widths)
  if (h.includes('manobras')) return { minWidth: '65px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('conhecidas')) return { minWidth: '65px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('quantidade')) return { minWidth: '70px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('dados')) return { minWidth: '50px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('maestria')) return { minWidth: '65px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('infusões')) return { minWidth: '60px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('itens')) return { minWidth: '55px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('fúria')) return { minWidth: '55px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('deslocamento')) return { minWidth: '70px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('artes') || h.includes('marciais')) return { minWidth: '60px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('ki') || h.includes('chi')) return { minWidth: '40px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('furtivo') || h.includes('sneak')) return { minWidth: '65px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('feitiçaria') || h.includes('sorcery')) return { minWidth: '65px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('invocações') || h.includes('invo')) return { minWidth: '70px', textAlign: 'center' as const, isFeature: false };
  if (h.includes('fôlego') || h.includes('retomar')) return { minWidth: '60px', textAlign: 'center' as const, isFeature: false };

  // Fallback for unknown text columns
  return { minWidth: '60px', textAlign: 'center' as const, isFeature: false };
};

// --- Components ---

const TraitRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex flex-col border-b border-[var(--stroke)] last:border-0 py-2">
    <span className="text-[10px] uppercase font-bold text-[var(--muted)] tracking-wider mb-1">{label}</span>
    <span className="text-sm text-[var(--text)] font-medium leading-tight">{value}</span>
  </div>
);

const FeatureBlock: React.FC<{ feature: Feature }> = ({ feature }) => {
  const isSubclass = feature.type === 'subclass';
  const content = feature.body || feature.text || "";
  
  // Colors: Class = Red/Flame, Subclass = Yellow/Spark
  const headerColor = isSubclass ? 'text-[var(--spark)] border-[var(--spark)]' : 'text-[var(--flame)] border-[var(--flame)]';
  const headerBg = isSubclass ? 'bg-[var(--spark)]/5' : 'bg-[var(--flame)]/5';

  return (
    <div className={`rounded border border-[var(--stroke)] mb-4 overflow-hidden shadow-sm bg-[var(--bg1)]`}>
      {/* Header */}
      <div className={`px-4 py-2 border-b ${headerColor} border-opacity-30 ${headerBg} flex justify-between items-center`}>
        <h3 className={`font-rpg text-lg font-bold ${isSubclass ? 'text-[var(--spark)]' : 'text-[var(--flame)]'}`}>
          Nível {feature.level}: {feature.title}
        </h3>
        {isSubclass && feature.subclassName && (
           <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)] opacity-70 border border-[var(--stroke)] px-2 py-0.5 rounded bg-[var(--bg0)]">
             {feature.subclassName}
           </span>
        )}
      </div>

      {/* Body */}
      <div className="p-4">
        <div 
          className="text-sm text-[var(--muted)] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: parseMarkdown(content) }} 
        />

        {/* Embedded Tables */}
        {feature.tables && feature.tables.length > 0 && (
          <div className="mt-6 space-y-6">
            {feature.tables.map((table, idx) => (
              <div key={idx} className="overflow-hidden rounded border border-[var(--stroke)] bg-[var(--bg0)]">
                 {table.title && (
                   <div className="bg-[var(--bg2)] px-3 py-1.5 border-b border-[var(--stroke)]">
                     <span className="text-xs font-bold uppercase text-[var(--ember)] tracking-wider">{table.title}</span>
                   </div>
                 )}
                 <div className="overflow-x-auto">
                   <table className="w-full text-left text-xs whitespace-nowrap">
                     <thead>
                       <tr className="bg-[var(--bg1)] border-b border-[var(--stroke)]">
                         {table.columns.map((col, cIdx) => (
                           <th key={cIdx} className="px-3 py-2 text-[var(--muted)] font-bold uppercase">{col}</th>
                         ))}
                       </tr>
                     </thead>
                     <tbody className="divide-y divide-[var(--stroke)]">
                       {table.rows.map((row, rIdx) => (
                         <tr key={rIdx} className="hover:bg-[var(--bg2)] transition-colors">
                           {row.map((cell, cellIdx) => (
                             <td key={cellIdx} className="px-3 py-2 text-[var(--text)]" dangerouslySetInnerHTML={{ __html: parseMarkdown(String(cell)) }} />
                           ))}
                         </tr>
                       ))}
                     </tbody>
                   </table>
                 </div>
              </div>
            ))}
          </div>
        )}

        {/* Links Footer */}
        {feature.links && feature.links.length > 0 && (
          <div className="mt-6 pt-4 border-t border-[var(--stroke)] flex flex-wrap justify-center gap-3">
            {feature.links.map((link, i) => {
              let icon = <LinkIcon className="w-3 h-3" />;
              let colorClass = "text-[var(--text)] border-[var(--stroke)] hover:border-[var(--ember)]";
              
              if (link.kind === 'spell') {
                icon = <Scroll className="w-3 h-3" />;
                colorClass = "text-purple-300 border-purple-900/50 hover:border-purple-400 bg-purple-900/10";
              } else if (link.kind === 'item') {
                icon = <Shield className="w-3 h-3" />;
                colorClass = "text-[var(--ember)] border-[var(--ember)]/30 hover:border-[var(--ember)] bg-[var(--ember)]/5";
              }

              return (
                <Link 
                  key={i} 
                  to={link.href}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-bold uppercase tracking-wide transition-all border bg-[var(--bg2)] shadow-sm ${colorClass}`}
                >
                  {icon}
                  {link.label}
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </div>
  );
};

const MulticlassCard: React.FC<{ data?: Multiclassing }> = ({ data }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!data) return null;
  return (
    <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg overflow-hidden shadow-sm mt-6">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 text-left hover:bg-[var(--bg2)] transition-colors group"
      >
        <div className="flex items-center gap-2">
           <Hammer className="w-4 h-4 text-[var(--muted)] group-hover:text-[var(--ember)]" />
           <span className="font-bold text-xs uppercase tracking-wider text-[var(--text)] group-hover:text-[var(--ember)]">Multiclasse</span>
        </div>
        <ChevronDown className={`w-4 h-4 text-[var(--muted)] transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="p-4 border-t border-[var(--stroke)] bg-[var(--bg0)] space-y-4">
           <div className="space-y-1">
             <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Pré-requisitos</span>
             <p className="text-xs text-[var(--text)] font-medium">{data.requirements}</p>
           </div>
           <div className="space-y-1">
             <span className="text-[10px] uppercase font-bold text-[var(--muted)]">Proficiências Adquiridas</span>
             <ul className="text-xs text-[var(--text)] space-y-1 list-disc list-inside">
                <li><strong>Armadura:</strong> {data.armorTraining || "Nenhuma"}</li>
                <li><strong>Ferramentas:</strong> {data.toolProficiencies || "Nenhuma"}</li>
                <li><strong>Perícias:</strong> {data.skillProficiencies || "Nenhuma"}</li>
             </ul>
           </div>
        </div>
      )}
    </div>
  );
};

// --- Main Page ---

const JogadorClasses: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
  const [classes, setClasses] = useState<ClassData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedClassSlug, setSelectedClassSlug] = useState<string | null>(null);
  const [selectedSubclassSlugs, setSelectedSubclassSlugs] = useState<string[]>([]);
  const [classSearchQuery, setClassSearchQuery] = useState('');
  const [searchQuery, setSearchQuery] = useState(''); // Feature search

  // 1. Fetch
  useEffect(() => {
    fetch('/data/classes.json')
      .then(res => {
        if (!res.ok) throw new Error("Falha ao carregar classes.");
        return res.json();
      })
      .then(data => {
        setClasses(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError("Não foi possível carregar o grimório de classes.");
        setLoading(false);
      });
  }, []);

  // 2. URL Sync
  useEffect(() => {
    if (loading || classes.length === 0) return;
    const params = new URLSearchParams(location.search);
    const classParam = params.get('c');
    const subclassParam = params.get('sc');
    
    if (classParam) {
      const found = classes.find(c => c.slug === classParam);
      if (found) setSelectedClassSlug(found.slug);
      else setSelectedClassSlug(classes[0].slug);
    } else {
      if (!selectedClassSlug) setSelectedClassSlug(classes[0].slug);
    }

    if (subclassParam) {
      const slugs = subclassParam.split(',').filter(s => s);
      setSelectedSubclassSlugs(slugs);
    } else {
      setSelectedSubclassSlugs([]);
    }
  }, [loading, classes, location.search]);

  // Derived state
  const activeClass = useMemo(() => classes.find(c => c.slug === selectedClassSlug), [classes, selectedClassSlug]);

  // Filtered Class List
  const filteredClasses = useMemo(() => {
    return [...classes]
      .sort((a, b) => a.name.localeCompare(b.name))
      .filter(c => c.name.toLowerCase().includes(classSearchQuery.toLowerCase()));
  }, [classes, classSearchQuery]);

  // Handlers
  const handleSelectClass = (slug: string) => {
    if (slug === selectedClassSlug) return;
    const newParams = new URLSearchParams();
    newParams.set('c', slug);
    navigate({ search: newParams.toString() });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const toggleSubclass = (slug: string) => {
    let newSelection = [...selectedSubclassSlugs];
    if (newSelection.includes(slug)) {
      newSelection = newSelection.filter(s => s !== slug);
    } else {
      newSelection.push(slug);
    }
    
    const params = new URLSearchParams(location.search);
    params.set('c', selectedClassSlug || '');
    if (newSelection.length > 0) params.set('sc', newSelection.join(','));
    else params.delete('sc');
    
    navigate({ search: params.toString() }, { replace: true });
  };

  // --- Table Logic (The Patch System) ---
  const tableData = useMemo(() => {
    if (!activeClass) return null;
    
    const base = activeClass.classTable.base;
    let finalColumns = [...base.columns];
    let finalRows = base.rows.map(r => [...r]); // clone rows
    
    // Check for active patch
    // Priority: First selected subclass that HAS a patch
    let activePatch: SubclassTablePatch | null = null;
    let patchSource = "";

    // Order of selection matters in UI, but here we just grab the first one that defines a patch
    for (const subSlug of selectedSubclassSlugs) {
        const sub = activeClass.subclasses.find(s => s.slug === subSlug);
        if (sub && sub.tablePatch) {
            activePatch = sub.tablePatch;
            patchSource = sub.name;
            break; 
        }
    }

    // Apply Patch
    let groupStartIndex = -1;
    let insertIndex = -1;

    if (activePatch && activePatch.mode === 'addColumns') {
        const { insertAfter, extraColumns, rowsByLevel } = activePatch;
        
        // Find insertion index
        insertIndex = finalColumns.findIndex(c => c === insertAfter);
        if (insertIndex === -1) insertIndex = finalColumns.length; // fallback to end
        else insertIndex += 1; // insert after

        // Insert Columns
        finalColumns.splice(insertIndex, 0, ...extraColumns);

        // Determine where the Group Start is
        // We assume the group header applies to the LAST N columns of the inserted batch
        // e.g. ["Truques", "Magias", "1º", "2º", "3º", "4º"] -> Group "Espaços" (span 4) applies to 1,2,3,4.
        if (activePatch.groupHeader) {
           const offset = extraColumns.length - activePatch.groupHeader.span;
           groupStartIndex = insertIndex + offset;
        }

        // Insert Data Row by Row
        finalRows = finalRows.map((row, idx) => {
            const level = row[0]; // Assuming col 0 is always level
            const patchData = rowsByLevel[String(level)];
            
            // Create a gap filler if no data for this level
            const dataToInsert = patchData || Array(extraColumns.length).fill("—");
            
            const newRow = [...row];
            newRow.splice(insertIndex, 0, ...dataToInsert);
            return newRow;
        });
    }

    return {
        columns: finalColumns,
        rows: finalRows,
        patchSource,
        groupHeader: activePatch?.groupHeader,
        insertIndex,
        groupStartIndex
    };
  }, [activeClass, selectedSubclassSlugs]);


  // --- Feature Processing ---
  const processedFeatures = useMemo(() => {
    if (!activeClass) return [];
    
    let list: Feature[] = [...activeClass.features];
    
    // Add subclass features
    activeClass.subclasses.forEach(sub => {
      if (selectedSubclassSlugs.includes(sub.slug)) {
        const subFeatures = sub.features.map(f => ({
          ...f,
          subclassSlug: sub.slug,
          subclassName: sub.name
        }));
        list = [...list, ...subFeatures];
      }
    });

    // Filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(f => f.title.toLowerCase().includes(q));
    }

    // Sort: Level -> Class Features -> Subclass Features -> Name
    list.sort((a, b) => {
      if (a.level !== b.level) return a.level - b.level;
      if (a.type !== b.type) return a.type === 'class' ? -1 : 1;
      return a.title.localeCompare(b.title);
    });

    return list;
  }, [activeClass, selectedSubclassSlugs, searchQuery]);


  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Carregando classes...</p>
    </div>
  );

  if (error || !activeClass || !tableData) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh]">
      <AlertTriangle className="w-10 h-10 text-[var(--flame)] mb-4" />
      <p className="text-[var(--muted)]">{error || "Classe não encontrada."}</p>
    </div>
  );

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-[var(--bg0)] items-start">
      
      {/* === LEFT SIDEBAR === */}
      <aside className="w-full md:w-64 lg:w-72 shrink-0 border-b md:border-b-0 md:border-r border-[var(--stroke)] bg-[var(--bg1)] p-4 flex flex-col gap-6 self-start">
        
        {/* Class Search & List */}
        <div className="flex flex-col gap-3"> 
          <div className="relative">
            <input 
              type="text"
              value={classSearchQuery}
              onChange={(e) => setClassSearchQuery(e.target.value)}
              placeholder="Buscar classe..."
              className="w-full bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--text)] font-medium text-xs py-2 pl-8 pr-2 rounded focus:border-[var(--ember)] focus:outline-none placeholder:text-[var(--muted)]/50"
            />
            <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-[var(--muted)]" />
          </div>

          <div className="flex flex-col gap-1">
            {filteredClasses.length > 0 ? (
              filteredClasses.map(c => {
                const isActive = c.slug === activeClass.slug;
                return (
                  <button 
                    key={c.slug}
                    onClick={() => handleSelectClass(c.slug)}
                    className={`
                      w-full text-left px-3 py-2 rounded text-sm font-bold uppercase tracking-wide transition-all border
                      ${isActive 
                        ? 'bg-[var(--bg0)] border-[var(--flame)] text-[var(--text)] shadow-[inset_3px_0_0_var(--flame)]' 
                        : 'bg-transparent border-transparent text-[var(--muted)] hover:bg-[var(--bg2)] hover:text-[var(--text)]'
                      }
                    `}
                  >
                    {c.name}
                  </button>
                )
              })
            ) : (
              <p className="text-xs text-[var(--muted)] text-center py-2">Nenhuma classe encontrada.</p>
            )}
          </div>
        </div>

        {/* Core Traits */}
        {activeClass && (
          <div className="bg-[var(--bg0)] border border-[var(--stroke)] rounded p-4 shadow-sm relative overflow-hidden">
             <div className="absolute top-0 left-0 w-1 h-full bg-[var(--flame)]"></div>
             <h2 className="font-rpg text-xl font-bold text-[var(--text)] mb-3 pl-2">{activeClass.name}</h2>
             <div className="space-y-1">
               {activeClass.coreTraits.map((trait, i) => (
                 <TraitRow key={i} label={trait.label} value={trait.value} />
               ))}
             </div>
          </div>
        )}

        {/* Multiclass */}
        {activeClass && <MulticlassCard data={activeClass.multiclassing} />}

      </aside>

      {/* === RIGHT CONTENT === */}
      <main className="flex-1 min-w-0 p-4 md:p-6 lg:p-8 flex flex-col gap-8">
        
        {/* 1. TABLE SECTION */}
        <div className="flex flex-col gap-4">
           <div className="flex justify-between items-end border-b border-[var(--stroke)] pb-2">
              <div>
                <h1 className="font-rpg text-3xl md:text-4xl font-bold text-[var(--text)]">{activeClass.name}</h1>
                <p className="text-[var(--muted)] text-sm italic">{activeClass.tagline}</p>
              </div>
              {tableData.patchSource && (
                 <div className="hidden md:flex items-center gap-2 px-2 py-1 rounded bg-[var(--bg2)] border border-[var(--spark)] text-[10px] font-bold uppercase text-[var(--spark)] animate-in fade-in">
                   <Info className="w-3 h-3" />
                   Tabela: {tableData.patchSource}
                 </div>
              )}
           </div>

           {/* --- MOBILE VIEW (Cards) --- */}
           <div className="md:hidden flex flex-col gap-4">
              {tableData.rows.map((row, rIdx) => {
                const level = row[0]; 
                
                return (
                  <div key={rIdx} className="bg-[var(--bg1)] border border-[var(--stroke)] rounded p-4 shadow-sm relative overflow-hidden">
                     {/* Decoration */}
                     <div className="absolute top-0 left-0 w-1 h-full bg-[var(--stroke)]"></div>
                     
                     {/* Header: Level & PB */}
                     <div className="flex items-center justify-between mb-3 pl-3">
                        <h3 className="font-rpg text-xl font-bold text-[var(--text)]">Nível {level}</h3>
                        {/* Find PB column if exists */}
                        {tableData.columns.map((c, i) => {
                           if (c.toLowerCase() === 'pb' || c.toLowerCase().includes('prof')) {
                             return <span key={i} className="text-xs font-bold text-[var(--muted)] border border-[var(--stroke)] px-2 py-1 rounded bg-[var(--bg0)]">PB: {row[i]}</span>
                           }
                           return null;
                        })}
                     </div>

                     {/* Features Row */}
                     <div className="pl-3 mb-4">
                        {tableData.columns.map((c, i) => {
                           if (getColumnStyle(c).isFeature) {
                              const val = String(row[i] || '—'); // Safety check
                              if (val === '—') return null;
                              return (
                                <div key={i} className="text-sm text-[var(--text)] leading-relaxed">
                                   <span className="text-[var(--ember)] font-bold mr-1">Habilidades:</span> 
                                   <span dangerouslySetInnerHTML={{ __html: parseMarkdown(val) }} />
                                </div>
                              )
                           }
                           return null;
                        })}
                     </div>

                     {/* Stats Grid (Everything else) */}
                     <div className="pl-3 grid grid-cols-3 sm:grid-cols-4 gap-2 border-t border-[var(--stroke)] pt-3">
                        {tableData.columns.map((c, i) => {
                           const style = getColumnStyle(c);
                           const isLevel = c.toLowerCase() === 'nível' || c.toLowerCase() === 'level';
                           const isPB = c.toLowerCase() === 'pb' || c.toLowerCase().includes('prof');
                           
                           if (style.isFeature || isLevel || isPB) return null;

                           return (
                             <div key={i} className="flex flex-col">
                                <span className="text-[10px] uppercase font-bold text-[var(--muted)] truncate" title={c}>{c}</span>
                                <span className="text-sm font-medium text-[var(--text)]" dangerouslySetInnerHTML={{ __html: parseMarkdown(String(row[i] || '—')) }} />
                             </div>
                           )
                        })}
                     </div>
                  </div>
                )
              })}
           </div>

           {/* --- DESKTOP VIEW (Table) --- */}
           {/* KEY FIX: Reduced font size to text-[11px] */}
           <div className="hidden md:block w-full overflow-x-auto rounded border border-[var(--stroke)] bg-[var(--bg1)] shadow-sm">
              <table className="w-full text-left text-[11px] border-collapse min-w-max table-auto">
                <thead className="bg-[var(--bg2)] text-[var(--ember)] border-b border-[var(--stroke)]">
                  {/* Robust Header Logic: Handle Grouping + Free Columns */}
                  {tableData.groupHeader && tableData.groupStartIndex !== -1 ? (
                    <>
                      <tr>
                        {tableData.columns.map((col, i) => {
                           // 1. If inside the group range (but NOT the first column of the group), skip render (covered by colspan)
                           if (i > tableData.groupStartIndex && i < tableData.groupStartIndex + tableData.groupHeader!.span) {
                               return null;
                           }
                           
                           // 2. If it IS the start of the group, render the Group Header
                           if (i === tableData.groupStartIndex) {
                              return (
                                <th 
                                  key={`group-${i}`}
                                  colSpan={tableData.groupHeader!.span} 
                                  className="px-2 py-2 border-b border-r border-[var(--stroke)] text-center bg-[var(--bg0)] text-[var(--muted)] text-[10px] font-bold uppercase tracking-widest align-middle whitespace-nowrap"
                                >
                                  {tableData.groupHeader!.label}
                                </th>
                              );
                           }

                           // 3. Otherwise, it's a standard column (Left or Right of group). Render with RowSpan 2.
                           const style = getColumnStyle(col);
                           return (
                             <th 
                               key={`std-${i}`}
                               rowSpan={2} 
                               style={{ minWidth: style.minWidth }}
                               className={`px-2 py-3 border-r border-[var(--stroke)] text-[10px] font-bold uppercase tracking-wider align-bottom whitespace-normal break-words leading-normal ${style.textAlign === 'center' ? 'text-center' : 'text-left'}`}
                             >
                               {formatHeader(col)}
                             </th>
                           );
                        })}
                      </tr>
                      {/* Sub-Header Row: Only for the grouped columns */}
                      <tr>
                        {tableData.columns.slice(tableData.groupStartIndex, tableData.groupStartIndex + tableData.groupHeader.span).map((col, i) => (
                           <th 
                             key={`sub-${i}`} 
                             style={{ minWidth: getColumnStyle(col).minWidth }}
                             className="px-2 py-2 border-r border-[var(--stroke)] text-center text-[10px] font-bold uppercase tracking-wider align-bottom whitespace-normal break-words leading-normal"
                           >
                             {formatHeader(col)}
                           </th>
                        ))}
                      </tr>
                    </>
                  ) : (
                    // Standard Single Row Header (No Groups)
                    <tr>
                      {tableData.columns.map((col, i) => {
                        const style = getColumnStyle(col);
                        return (
                          <th 
                            key={i} 
                            style={{ minWidth: style.minWidth }}
                            className={`px-2 py-3 border-r border-[var(--stroke)] text-[10px] font-bold uppercase tracking-wider align-bottom whitespace-normal break-words leading-normal ${style.textAlign === 'center' ? 'text-center' : 'text-left'}`}
                          >
                            {formatHeader(col)}
                          </th>
                        );
                      })}
                    </tr>
                  )}
                </thead>
                <tbody className="divide-y divide-[var(--stroke)] text-[var(--text)]">
                  {tableData.rows.map((row, rI) => (
                    <tr key={rI} className="hover:bg-[var(--bg2)] even:bg-[var(--bg0)]/30 transition-colors">
                      {row.map((cell, cI) => {
                        const colName = tableData.columns[cI];
                        const style = getColumnStyle(colName);
                        return (
                          <td 
                            key={cI} 
                            className={`p-1.5 border-r border-[var(--stroke)] last:border-r-0 leading-snug align-top ${style.isFeature ? 'whitespace-normal break-words text-left' : 'whitespace-nowrap text-center'}`}
                          >
                            {cell}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
           </div>
        </div>

        {/* 2. SUBCLASSES SELECTOR */}
        <div className="flex flex-col gap-2">
           <h3 className="text-xs font-bold text-[var(--muted)] uppercase tracking-widest flex items-center gap-2">
             <Layers className="w-3 h-3" /> Subclasses (Selecione para ver)
           </h3>
           <div className="flex flex-wrap gap-2">
             {activeClass.subclasses.map(sub => {
               const isSelected = selectedSubclassSlugs.includes(sub.slug);
               return (
                 <button
                   key={sub.slug}
                   onClick={() => toggleSubclass(sub.slug)}
                   className={`
                     px-4 py-2 rounded text-xs font-bold uppercase tracking-wide border transition-all shadow-sm
                     ${isSelected 
                       ? 'bg-[var(--ember)] border-[var(--ember)] text-white hover:brightness-110' 
                       : 'bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)] hover:border-[var(--muted)] hover:text-[var(--text)]'}
                   `}
                 >
                   {sub.name}
                 </button>
               )
             })}
           </div>
        </div>

        {/* 3. FEATURES LIST */}
        <div className="space-y-6">
           {/* Search in Features */}
           <div className="relative">
             <input 
               type="text" 
               placeholder="Filtrar habilidades..." 
               value={searchQuery}
               onChange={(e) => setSearchQuery(e.target.value)}
               className="w-full bg-transparent border-b border-[var(--stroke)] py-2 pl-8 text-sm text-[var(--text)] focus:border-[var(--ember)] outline-none"
             />
             <Search className="absolute left-0 top-2.5 w-4 h-4 text-[var(--muted)]" />
           </div>

           {processedFeatures.length === 0 ? (
             <div className="py-12 text-center border border-dashed border-[var(--stroke)] rounded text-[var(--muted)]">
               Nenhuma habilidade encontrada.
             </div>
           ) : (
             <div className="flex flex-col gap-2">
               {processedFeatures.map((feature, idx) => (
                 <FeatureBlock key={`${feature.title}-${idx}`} feature={feature} />
               ))}
             </div>
           )}
        </div>

      </main>
    </div>
  );
};

export default JogadorClasses;