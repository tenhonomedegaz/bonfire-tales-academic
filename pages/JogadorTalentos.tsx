import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Search, 
  Filter, 
  ArrowUpDown, 
  Zap, 
  Loader2, 
  AlertTriangle, 
  X, 
  ChevronRight, 
  Check,
  Flame,
  Info,
  BookOpen,
  ArrowLeft,
  HelpCircle,
  Dna,
  XCircle,
  ScrollText
} from 'lucide-react';

// --- Types ---

interface MetaContent {
  title: string;
  subtitle: string;
  body: string[];
  bullets: string[];
  tables?: {
    title: string;
    columns: string[];
    rows: string[][];
  }[];
}

interface MetaInfo {
  marks: MetaContent;
  categories: MetaContent;
}

interface TalentTable {
  title: string;
  columns: string[];
  rows: string[][];
}

interface TalentLink {
  label: string;
  href: string;
  kind: 'rule' | 'item' | 'spell';
}

interface AbilityIncrease {
  type: 'fixed' | 'choice' | 'none';
  options?: string[];
  amount?: number;
}

interface SpellList {
  title: string;
  kind: 'alwaysPrepared' | 'addedToClass';
  progression: {
    level: number;
    spells: string[];
  }[];
}

interface TalentSection {
  title: string;
  body: string[];
}

interface StructuredBenefit {
  label: string;
  text: string;
}

interface Talent {
  name: string;
  slug: string;
  category: "Origem" | "Geral" | "Épico";
  tags: string[];
  abilityIncrease?: AbilityIncrease;
  prerequisites: string[];
  source: string;
  short: string;
  description: string[];
  effectTitle: string;
  effect?: string[]; // Legacy support
  benefits?: StructuredBenefit[]; // New structured support
  sections?: TalentSection[];
  spellLists?: SpellList[];
  tables?: TalentTable[];
  links?: TalentLink[];
}

interface TalentData {
  meta: {
    info: MetaInfo;
  };
  talentos: Talent[];
}

// View Mode State for the Detail Card
type DetailMode = 
  | { type: 'talent' } 
  | { type: 'help'; topic: 'marcas' | 'origem' | 'geral' | 'epico' };

// --- Constants (Help Text) ---

const HELP_CONTENT = {
  marcas: {
    title: "Marcas Místicas em Cineria",
    sections: [
      {
        title: "O Fluxo e os Selos",
        text: "Em Cineria, magia não é só “conjurar um feitiço”. Ela é o fluxo de mana correndo pela Trama, atravessando limiares, portais e véus. Para que esse fluxo não rasgue a Criação, Asterios, o Tecelão dos Planos, inscreveu limites, selos e regras na própria Trama, mantendo a magia útil e segura mesmo quando o mundo atravessou eras de crise."
      },
      {
        title: "A Origem das Marcas",
        text: "Essas regras não foram escritas apenas como teoria. Em momentos raros e decisivos, Asterios reforçou grades do Umbral, ancorou leylines e deixou “moldes” na Trama para que mortais canalizassem mana sem colapso. É dessa camada de decretos, protocolos e lacres que nascem as Marcas Arcanas: fragmentos de um conceito mágico que, por acaso de linhagem, nascimento ou vida, se prendem à alma de alguém e despertam como uma runa no corpo."
      },
      {
        title: "Sintonia, não Herança",
        text: "Por isso, Marcas Arcanas não pertencem a uma raça, nação ou clã específico. Elas são sinais de sintonia com um decreto do Arcano. Quando surgem, costumam acompanhar pessoas que acabam cruzando portas importantes demais, encarando verdades que ninguém queria ver, ou carregando responsabilidades que o mundo não distribui ao acaso. E, como todo selo verdadeiro, elas não existem para “dar poder de graça”: elas existem para lembrar que magia tem gramática, custo e retorno."
      },
      {
        title: "Como as Marcas funcionam no servidor",
        text: "As Marcas são tratadas como um Talento de Origem que representa esse “selo vivo” na alma do personagem. Elas concedem intuições, resistências e magias inatas ligadas ao tema da Marca, sem substituir a identidade da sua classe. A aparência da runa, o modo como ela desperta e o impacto social disso na sua história são parte do roleplay do personagem."
      },
      {
        title: "Regras de Marcas",
        bullets: [
          "Uma Marca por personagem: você escolhe uma Marca Arcana ou a Marca Anômala. Personagens com uma Marca não podem acessar outra Marca.",
          "Runa manifesta: ao despertar, surge uma runa visível no corpo. Você define o local, a forma e como ela “reage” (calor, brilho, frio, pulsar etc.).",
          "Mecânica fixa, narrativa livre: os efeitos do talento não mudam, mas o visual, a origem e o significado na história podem variar.",
          "Gancho de trama: Marcas atraem curiosidade de templos, academias e gente que coleciona segredos. Isso é intencional e serve como combustível para histórias."
        ]
      },
      {
        title: "Marca Anômala",
        text: "A Marca Anômala não é um decreto “limpo” do Arcano. Ela nasce de anomalias na Trama onde o Plano Umbral pressiona a realidade e onde a Magia Sombria encontra brechas. Por isso, ela tende a rechaçar as Marcas Arcanas como forças opostas, e seus portadores quase sempre carregam um preço junto do dom: sonhos intrusivos, sensações de vazio, dor espiritual, mudanças de percepção. Em troca, a Marca Anômala cria uma afinidade instável com aquilo que vive por baixo do Véu, e esse tipo de poder raramente vem sem consequência."
      }
    ]
  },
  origem: {
    title: "Talentos de Origem",
    sections: [
      {
        text: "Talentos de Origem representam o que você trouxe para a aventura antes da fama: criação, cultura, ofício, disciplina, sobrevivência e hábitos de vida. Eles tendem a oferecer proficiências, pequenos recursos, truques, vantagens situacionais e usos por descanso, reforçando identidade e utilidade desde cedo."
      }
    ]
  },
  geral: {
    title: "Talentos Gerais",
    sections: [
      {
        text: "Talentos Gerais são escolhas de especialização que representam treino, experiência e técnicas consolidadas durante a vida de aventura. Quando um talento conceder Aumento de Atributo, você aumenta o atributo indicado em +1, mas nunca pode ultrapassar 20 (se já tiver 20, você não ganha aquele aumento, a menos que o talento permita escolher outro atributo). Pré-requisitos, recargas por Descanso Curto ou Descanso Longo, e quaisquer CDs, ações e condições seguem exatamente o que estiver descrito no talento."
      },
      {
        text: "Em termos de jogo, Talentos Gerais servem para ajustar seu estilo: melhorar combate, mobilidade, defesa, utilidade, suporte ou conjuração."
      }
    ]
  },
  epico: {
    title: "Talentos Épicos",
    sections: [
      {
        text: "Talentos Épicos são raros e ligados a feitos grandiosos, juramentos, bênçãos, pactos ou conquistas que mudam a escala da sua lenda e concedem efeitos marcantes, com impacto real no rumo de uma aventura."
      },
      {
        text: "A regra do Aumento de Atributo para esse talento é alterada para oferecer +2 em um atributo, e ele não pode passar de 22. Usos por descanso, ações, reações, CDs e exceções funcionam exatamente como escrito, e não se acumulam fora do que o texto permite."
      }
    ]
  }
};

// --- Helpers ---

const parseMarkdown = (text: string) => {
  if (!text) return "";
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong class="text-[var(--text)] font-bold">$1</strong>')
    .replace(/^\* (.*$)/gim, '<li class="ml-4 list-disc marker:text-[var(--ember)]">$1</li>');
};

// --- Components ---

const FilterModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  data: Talent[];
  filters: {
    categories: string[];
    tags: string[];
    abilities: string[];
  };
  setFilters: React.Dispatch<React.SetStateAction<{
    categories: string[];
    tags: string[];
    abilities: string[];
  }>>;
}> = ({ isOpen, onClose, data, filters, setFilters }) => {
  
  const options = useMemo(() => {
    const cats = new Set<string>();
    const tags = new Set<string>();
    const abilities = ["Força", "Destreza", "Constituição", "Inteligência", "Sabedoria", "Carisma"];

    data.forEach(t => {
      cats.add(t.category);
      t.tags.forEach(tag => tags.add(tag));
    });

    return {
      categories: Array.from(cats).sort(),
      tags: Array.from(tags).sort(),
      abilities
    };
  }, [data]);

  const [localFilters, setLocalFilters] = useState(filters);

  useEffect(() => {
    if (isOpen) setLocalFilters(filters);
  }, [isOpen, filters]);

  const toggleFilter = (type: 'categories' | 'tags' | 'abilities', value: string) => {
    setLocalFilters(prev => {
      const current = prev[type];
      const updated = current.includes(value)
        ? current.filter(item => item !== value)
        : [...current, value];
      return { ...prev, [type]: updated };
    });
  };

  const clearAll = () => {
    setLocalFilters({ categories: [], tags: [], abilities: [] });
  };

  const apply = () => {
    setFilters(localFilters);
    onClose();
  };

  if (!isOpen) return null;

  const FilterSection = ({ title, type, items }: { title: string, type: 'categories' | 'tags' | 'abilities', items: string[] }) => (
    <div className="mb-6">
      <div className="flex justify-between items-center mb-3 border-b border-[var(--stroke)] pb-1">
        <h4 className="text-xs font-bold uppercase text-[var(--muted)] tracking-widest">{title}</h4>
        {localFilters[type].length > 0 && (
           <button onClick={() => setLocalFilters(prev => ({...prev, [type]: []}))} className="text-[10px] uppercase font-bold text-[var(--flame)] hover:underline">Limpar</button>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map(item => {
          const isSelected = localFilters[type].includes(item);
          return (
            <button
              key={item}
              onClick={() => toggleFilter(type, item)}
              className={`
                px-3 py-1.5 rounded text-xs font-bold border transition-all flex items-center gap-2
                ${isSelected 
                  ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)] ring-1 ring-[var(--ember)]' 
                  : 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] hover:border-[var(--muted)] hover:text-[var(--text)]'}
              `}
            >
              {item}
              {isSelected && <Check className="w-3 h-3 text-[var(--ember)]" />}
            </button>
          )
        })}
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg shadow-2xl flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-200">
        <div className="p-4 border-b border-[var(--stroke)] flex justify-between items-center bg-[var(--bg2)] rounded-t-lg">
          <h3 className="font-rpg text-lg font-bold text-[var(--text)] flex items-center gap-2">
            <Filter className="w-4 h-4 text-[var(--ember)]" />
            Filtros
          </h3>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)]">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
          <FilterSection title="Categoria" type="categories" items={options.categories} />
          <FilterSection title="Aumento de Atributo" type="abilities" items={options.abilities} />
          <FilterSection title="Tags" type="tags" items={options.tags} />
        </div>
        <div className="p-4 border-t border-[var(--stroke)] bg-[var(--bg2)] rounded-b-lg flex gap-3">
          <button onClick={clearAll} className="px-4 py-2.5 border border-[var(--stroke)] bg-[var(--bg1)] text-[var(--muted)] hover:text-[var(--text)] font-bold rounded text-sm transition-colors">Limpar Tudo</button>
          <button onClick={apply} className="flex-1 py-2.5 bg-[var(--ember)] hover:bg-[var(--flame)] text-white font-bold rounded text-sm shadow-lg transition-all">Aplicar Filtros</button>
        </div>
      </div>
    </div>
  );
};

const TalentDetail: React.FC<{ 
  talent?: Talent; 
  hasMarkFilterActive: boolean;
  viewMode: DetailMode;
  setViewMode: (mode: DetailMode) => void;
}> = ({ talent, hasMarkFilterActive, viewMode, setViewMode }) => {
  
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [talent, viewMode]);

  // --- HELP MODE VIEW ---
  if (viewMode.type === 'help') {
    const content = HELP_CONTENT[viewMode.topic];
    return (
      <div ref={containerRef} className="absolute inset-0 overflow-y-auto custom-scrollbar p-6 md:p-10 animate-in fade-in duration-300 bg-[var(--bg0)]">
        
        {/* Header with Back Button */}
        <div className="flex items-center justify-between mb-8 border-b border-[var(--stroke)] pb-4">
          <h2 className="font-rpg text-3xl font-bold text-[var(--ember)]">{content.title}</h2>
          <button 
            onClick={() => setViewMode({ type: 'talent' })}
            className="flex items-center gap-2 px-4 py-2 rounded bg-[var(--bg1)] border border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)] transition-colors text-sm font-bold uppercase tracking-wide"
          >
            <ArrowLeft className="w-4 h-4" />
            Voltar ao Talento
          </button>
        </div>

        {/* Content Body */}
        <div className="space-y-8 max-w-3xl">
          {content.sections.map((section, idx) => (
            <div key={idx}>
              {section.title && (
                <h3 className="text-xl font-bold text-[var(--text)] mb-3 flex items-center gap-2">
                  <ScrollText className="w-5 h-5 text-[var(--muted)]" />
                  {section.title}
                </h3>
              )}
              {section.text && (
                <p className="text-[var(--muted)] leading-relaxed text-base mb-4">
                  {section.text}
                </p>
              )}
              {section.bullets && (
                <ul className="space-y-3 mt-2 bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
                  {section.bullets.map((bullet, bIdx) => (
                    <li key={bIdx} className="flex gap-3 text-sm text-[var(--text)] leading-relaxed">
                      <span className="text-[var(--ember)] font-bold">•</span>
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // --- TALENT MODE VIEW ---

  if (!talent) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-[var(--muted)] opacity-50 p-8 text-center border border-dashed border-[var(--stroke)] rounded m-4 bg-[var(--bg1)]/30">
        <Zap className="w-16 h-16 mb-4" />
        <p className="text-lg font-rpg">Selecione um talento na lista para ver os detalhes.</p>
      </div>
    );
  }

  const isMark = talent.tags.includes("Marca");
  const showMarkHelp = isMark || hasMarkFilterActive;
  
  let categoryTopic: 'origem' | 'geral' | 'epico' | null = null;
  if (talent.category === 'Origem') categoryTopic = 'origem';
  if (talent.category === 'Geral') categoryTopic = 'geral';
  if (talent.category === 'Épico') categoryTopic = 'epico';

  // Helper to render benefits cleanly
  const renderBenefitContent = () => {
    // 1. Try structured benefits
    if (talent.benefits && talent.benefits.length > 0) {
      return talent.benefits.map((b, i) => (
        <div key={i} className="mb-3 text-sm leading-relaxed">
          <strong className="text-[var(--text)] font-bold">{b.label}: </strong>
          <span className="text-[var(--muted)] font-normal">{b.text}</span>
        </div>
      ));
    }

    // 2. Fallback to legacy 'effect' array with runtime parsing
    if (talent.effect && talent.effect.length > 0) {
      return talent.effect.map((line, i) => {
        const parts = line.split(':');
        if (parts.length > 1) {
          const label = parts[0];
          const text = parts.slice(1).join(':');
          return (
            <div key={i} className="mb-3 text-sm leading-relaxed">
              <strong className="text-[var(--text)] font-bold">{label}: </strong>
              <span className="text-[var(--muted)] font-normal">{text}</span>
            </div>
          );
        }
        return (
          <p key={i} className="mb-3 text-sm text-[var(--muted)] leading-relaxed font-normal" dangerouslySetInnerHTML={{ __html: parseMarkdown(line) }} />
        );
      });
    }
    return null;
  };

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-y-auto custom-scrollbar p-6 md:p-10 animate-in fade-in duration-300">
      
      {/* Header */}
      <div className="border-b border-[var(--stroke)] pb-6 mb-8">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
          <div className="flex flex-wrap gap-2 items-center">
            {/* Category Chip */}
            <span className="px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest border bg-[var(--bg2)] text-[var(--ember)] border-[var(--ember)]">
              {talent.category}
            </span>
            {/* Tag Chips */}
            {talent.tags.map(tag => (
              <span key={tag} className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-widest border ${tag === 'Marca' ? 'bg-purple-900/20 text-purple-400 border-purple-500/50' : 'bg-[var(--bg1)] text-[var(--muted)] border-[var(--stroke)]'}`}>
                {tag}
              </span>
            ))}
          </div>
          
          <div className="flex gap-2">
            {/* Category Help Button */}
            {categoryTopic && (
              <button 
                onClick={() => setViewMode({ type: 'help', topic: categoryTopic! })}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full border bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--ember)] hover:border-[var(--ember)] transition-colors text-xs font-bold"
                title={`O que é um Talento ${talent.category}?`}
              >
                <HelpCircle className="w-3 h-3" />
                {talent.category}?
              </button>
            )}

            {/* Mark Help Button */}
            {showMarkHelp && (
              <button 
                onClick={() => setViewMode({ type: 'help', topic: 'marcas' })}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full border text-xs font-bold transition-all shadow-sm bg-[var(--bg1)] border-[var(--stroke)] text-[var(--muted)] hover:text-purple-400 hover:border-purple-400"
              >
                <BookOpen className="w-3 h-3" />
                O que são Marcas?
              </button>
            )}
          </div>
        </div>

        <h1 className="font-rpg text-4xl font-bold text-[var(--text)] mb-2">{talent.name}</h1>
        <p className="text-lg text-[var(--muted)] italic">{talent.short}</p>
      </div>

      {/* Stats Block (Prerequisites + Ability Increase) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
        <div className="bg-[var(--bg1)] p-4 rounded border border-[var(--stroke)]">
          <span className="text-[10px] font-bold uppercase text-[var(--muted)] block mb-1">Pré-requisitos</span>
          <div className="text-sm font-medium text-[var(--text)]">
            {talent.prerequisites.length > 0 ? talent.prerequisites.join(", ") : "Nenhum"}
          </div>
        </div>
        <div className="bg-[var(--bg1)] p-4 rounded border border-[var(--stroke)]">
          <span className="text-[10px] font-bold uppercase text-[var(--muted)] block mb-1">Aumento de Atributo</span>
          <div className="text-sm font-medium text-[var(--text)] flex items-center gap-2">
            {talent.abilityIncrease ? (
                <>
                  <Dna className="w-4 h-4 text-[var(--spark)]" />
                  {talent.abilityIncrease.type === 'none' && <span>Nenhum</span>}
                  {talent.abilityIncrease.type === 'fixed' && (
                    <span>+{talent.abilityIncrease.amount} {talent.abilityIncrease.options?.join(", ")}</span>
                  )}
                  {talent.abilityIncrease.type === 'choice' && (
                    <span>+{talent.abilityIncrease.amount} em: {talent.abilityIncrease.options?.join(" ou ")}</span>
                  )}
                </>
            ) : (
                <span>Nenhum</span>
            )}
          </div>
        </div>
      </div>

      {/* Description */}
      <div className="prose prose-invert max-w-none text-[var(--muted)] leading-relaxed mb-8">
        {talent.description.map((p, i) => <p key={i} dangerouslySetInnerHTML={{ __html: parseMarkdown(p) }} />)}
      </div>

      {/* Effect Card */}
      <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg p-6 relative overflow-hidden group hover:border-[var(--ember)] transition-colors shadow-lg">
        <div className="absolute top-0 left-0 w-1 h-full bg-[var(--ember)]"></div>
        <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-4 flex items-center gap-2">
          <Flame className="w-5 h-5 text-[var(--ember)]" />
          Habilidade: {talent.effectTitle}
        </h3>
        {/* Render Benefits with Correct Formatting */}
        <div className="text-sm space-y-3">
          {renderBenefitContent()}
        </div>
      </div>

      {/* Extra Sections */}
      {talent.sections && talent.sections.map((sec, i) => (
        <div key={i} className="mt-8">
           <h4 className="font-bold text-[var(--text)] mb-2 uppercase text-xs tracking-wider border-b border-[var(--stroke)] pb-1 inline-block">{sec.title}</h4>
           <div className="text-sm text-[var(--muted)] space-y-2 mt-2">
             {sec.body.map((p, j) => <p key={j} dangerouslySetInnerHTML={{ __html: parseMarkdown(p) }} />)}
           </div>
        </div>
      ))}

      {/* Spell Lists */}
      {talent.spellLists && talent.spellLists.map((list, i) => (
        <div key={i} className="mt-8">
           <h4 className="font-bold text-[var(--text)] mb-3 text-sm uppercase tracking-wide flex items-center gap-2">
             <Zap className="w-4 h-4 text-purple-400" />
             {list.title}
           </h4>
           <div className="overflow-x-auto rounded border border-[var(--stroke)]">
             <table className="w-full text-left text-sm">
               <thead className="bg-[var(--bg2)] text-purple-400 font-bold uppercase text-xs">
                 <tr>
                   <th className="px-4 py-3 border-b border-[var(--stroke)] w-20">Nível</th>
                   <th className="px-4 py-3 border-b border-[var(--stroke)]">Magias</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-[var(--stroke)] bg-[var(--bg1)]">
                 {list.progression.map((row, r) => (
                   <tr key={r}>
                     <td className="px-4 py-3 text-[var(--text)] font-bold text-center">{row.level}</td>
                     <td className="px-4 py-3 text-[var(--muted)]">{row.spells.join(", ")}</td>
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
        </div>
      ))}

      {/* Tables */}
      {talent.tables?.map((table, i) => (
        <div key={i} className="mt-8">
          <h4 className="font-bold text-[var(--text)] mb-3 text-sm uppercase tracking-wide">{table.title}</h4>
          <div className="overflow-x-auto rounded border border-[var(--stroke)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg2)] text-[var(--ember)] font-bold uppercase text-xs">
                <tr>
                  {table.columns.map((col, c) => <th key={c} className="px-4 py-3 border-b border-[var(--stroke)]">{col}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--stroke)] bg-[var(--bg1)]">
                {table.rows.map((row, r) => (
                  <tr key={r}>
                    {row.map((cell, c) => <td key={c} className="px-4 py-3 text-[var(--muted)]">{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Links */}
      {talent.links && talent.links.length > 0 && (
        <div className="mt-8 pt-6 border-t border-[var(--stroke)] flex flex-wrap gap-3">
          {talent.links.map((link, i) => (
            <a 
              key={i} 
              href={link.href} 
              className="px-3 py-1.5 rounded text-xs font-bold border border-[var(--stroke)] bg-[var(--bg1)] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--text)] transition-colors flex items-center gap-2"
            >
              {link.kind === 'rule' && <BookOpen className="w-3 h-3" />}
              {link.label}
            </a>
          ))}
        </div>
      )}

    </div>
  );
};

// --- Main Page ---

const JogadorTalentos: React.FC = () => {
  const [data, setData] = useState<TalentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [filters, setFilters] = useState<{
    categories: string[];
    tags: string[];
    abilities: string[];
  }>({ categories: [], tags: [], abilities: [] });
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Selection & View Mode State
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<DetailMode>({ type: 'talent' });
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  // Fetch Data
  useEffect(() => {
    fetch('/data/talentos.json')
      .then(res => {
        if (!res.ok) throw new Error("Falha ao carregar talentos.");
        return res.json();
      })
      .then((jsonData) => {
        setData(jsonData);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setError("Não foi possível carregar os talentos.");
        setLoading(false);
      });
  }, []);

  // Filtering Logic
  const filteredTalents = useMemo(() => {
    if (!data) return [];
    
    let result = [...data.talentos];

    // Search
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      result = result.filter(t => 
        t.name.toLowerCase().includes(q) ||
        t.tags.some(tag => tag.toLowerCase().includes(q)) ||
        t.category.toLowerCase().includes(q) ||
        t.prerequisites.some(p => p.toLowerCase().includes(q))
      );
    }

    // Filter Groups
    if (filters.categories.length > 0) {
      result = result.filter(t => filters.categories.includes(t.category));
    }
    if (filters.tags.length > 0) {
      result = result.filter(t => t.tags.some(tag => filters.tags.includes(tag)));
    }
    if (filters.abilities.length > 0) {
      result = result.filter(t => {
        if (!t.abilityIncrease || t.abilityIncrease.type === 'none') return false;
        // Check exact match in fixed or any match in choice options
        return t.abilityIncrease.options?.some(opt => filters.abilities.includes(opt));
      });
    }

    // Sort
    result.sort((a, b) => sortOrder === 'asc' 
      ? a.name.localeCompare(b.name)
      : b.name.localeCompare(a.name)
    );

    return result;
  }, [data, searchTerm, filters, sortOrder]);

  const activeTalent = useMemo(() => 
    data?.talentos.find(t => t.slug === selectedSlug), 
  [data, selectedSlug]);

  const hasMarkFilterActive = useMemo(() => 
    filters.tags.includes("Marca"),
  [filters.tags]);

  const handleSelect = (slug: string) => {
    if (selectedSlug === slug) return; 
    setSelectedSlug(slug);
    setViewMode({ type: 'talent' }); // Always reset to talent view when selecting new item
    if (window.innerWidth < 768) setIsMobileDetailOpen(true);
  };

  const activeFilterCount = filters.categories.length + filters.tags.length + filters.abilities.length;

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Consultando pergaminhos...</p>
    </div>
  );

  if (error || !data) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <AlertTriangle className="w-10 h-10 text-[var(--flame)]" />
      <p className="text-[var(--muted)]">{error}</p>
    </div>
  );

  return (
    <main className="flex flex-col h-[calc(100vh-64px)] bg-[var(--bg0)] overflow-hidden">
      
      {/* --- Toolbar --- */}
      <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20 shadow-sm">
        <div className="container mx-auto max-w-7xl">
          <div className="mb-4">
            <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Talentos</h1>
            <p className="text-[var(--muted)] text-sm">Habilidades especiais, marcas e poderes de origem.</p>
          </div>

          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-grow">
              <input 
                type="text" 
                placeholder="Buscar talento, tag, requisito..." 
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-[var(--bg0)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none transition-colors"
              />
              <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
            </div>
            
            <div className="flex gap-2 shrink-0">
               <button 
                 onClick={() => setIsFilterOpen(true)} 
                 className={`flex items-center gap-2 px-4 py-2 rounded border text-sm font-medium transition-colors ${activeFilterCount > 0 ? 'bg-[var(--bg2)] border-[var(--ember)] text-[var(--text)]' : 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)]'}`}
               >
                 <Filter className="w-4 h-4" />
                 <span>Filtros</span>
                 {activeFilterCount > 0 && (
                   <span className="bg-[var(--ember)] text-white text-[10px] w-5 h-5 rounded-full flex items-center justify-center -mr-1">
                     {activeFilterCount}
                   </span>
                 )}
               </button>
               
               <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg0)] border border-[var(--stroke)] rounded text-[var(--muted)] hover:text-[var(--text)] transition-colors text-sm font-medium w-[80px] justify-center">
                 <ArrowUpDown className="w-4 h-4" />
                 <span>{sortOrder === 'asc' ? 'A-Z' : 'Z-A'}</span>
               </button>
            </div>
          </div>
        </div>
      </div>

      {/* --- Main Content Grid --- */}
      <div className="flex-1 flex overflow-hidden container mx-auto max-w-7xl md:px-4">
        
        {/* Left Column: List */}
        <div className="w-full md:w-1/3 lg:w-80 flex-shrink-0 flex flex-col border-r border-[var(--stroke)] bg-[var(--bg0)] md:bg-[var(--bg1)]/30">
           <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
             {filteredTalents.length > 0 ? (
               filteredTalents.map(t => {
                 const isSelected = selectedSlug === t.slug;
                 const isMark = t.tags.includes("Marca");
                 return (
                   <button
                     key={t.slug}
                     onClick={() => handleSelect(t.slug)}
                     className={`w-full text-left px-3 py-3 rounded border transition-all duration-200 group flex flex-col gap-1.5 ${
                       isSelected 
                         ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                         : 'bg-transparent border-transparent hover:bg-[var(--bg1)] hover:border-[var(--stroke)]'
                     }`}
                   >
                     <div className="flex justify-between items-start w-full">
                        <span className={`text-sm font-bold leading-tight ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                          {t.name}
                        </span>
                        <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border ml-2 shrink-0 ${isMark ? 'border-purple-500/50 text-purple-400 bg-purple-900/10' : 'border-[var(--stroke)] bg-[var(--bg0)] text-[var(--muted)]'}`}>
                          {t.category}
                        </span>
                     </div>
                     
                     <div className="flex flex-wrap gap-1">
                        {t.tags.slice(0, 3).map(tag => (
                          <span key={tag} className="text-[9px] text-[var(--muted)] opacity-60 bg-[var(--bg0)] px-1 rounded truncate max-w-[80px]">
                            {tag}
                          </span>
                        ))}
                     </div>
                   </button>
                 );
               })
             ) : (
               <div className="text-center py-10 text-[var(--muted)] text-sm px-4">
                 Nenhum talento encontrado com estes filtros.
               </div>
             )}
           </div>
        </div>

        {/* Right Column: Detail */}
        <div className="hidden md:flex flex-1 flex-col bg-[var(--bg0)] relative overflow-hidden">
           <TalentDetail 
             talent={activeTalent} 
             hasMarkFilterActive={hasMarkFilterActive}
             viewMode={viewMode}
             setViewMode={setViewMode}
           />
        </div>

      </div>

      {/* --- Mobile Detail Modal --- */}
      {isMobileDetailOpen && (
        <div className="fixed inset-0 z-50 md:hidden bg-[var(--bg0)] flex flex-col animate-in slide-in-from-bottom duration-300">
           {/* Mobile Header */}
           <div className="flex items-center justify-between p-4 border-b border-[var(--stroke)] bg-[var(--bg1)] shrink-0">
             <button onClick={() => setIsMobileDetailOpen(false)} className="flex items-center gap-2 text-[var(--muted)] hover:text-[var(--text)]">
               <ChevronRight className="w-5 h-5 rotate-180" />
               <span className="font-bold uppercase text-xs tracking-wider">Voltar</span>
             </button>
           </div>
           
           {/* Mobile Body */}
           <div className="flex-1 relative">
             <TalentDetail 
               talent={activeTalent} 
               hasMarkFilterActive={hasMarkFilterActive}
               viewMode={viewMode}
               setViewMode={setViewMode}
             />
           </div>
        </div>
      )}

      {/* --- Filter Modal --- */}
      <FilterModal 
        isOpen={isFilterOpen}
        onClose={() => setIsFilterOpen(false)}
        data={data?.talentos || []}
        filters={filters}
        setFilters={setFilters}
      />

    </main>
  );
};

export default JogadorTalentos;