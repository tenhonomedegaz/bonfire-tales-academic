
import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, Filter, ArrowUpDown, Loader2, AlertTriangle, ChevronRight, Layers, ChevronDown, ShieldQuestion, PlusCircle, MinusCircle
} from 'lucide-react';
import { Familiar, FamiliarData } from '../types';

// Simple deep merge helper
const mergeDeep = (target: any, source: any) => {
  const output = { ...target };
  if (isObject(target) && isObject(source)) {
    Object.keys(source).forEach(key => {
      if (isObject(source[key])) {
        if (!(key in target))
          Object.assign(output, { [key]: source[key] });
        else
          output[key] = mergeDeep(target[key], source[key]);
      } else {
        Object.assign(output, { [key]: source[key] });
      }
    });
  }
  return output;
};

const isObject = (item: any) => {
  return (item && typeof item === 'object' && !Array.isArray(item));
};

const getAbilityModifier = (score: number) => {
    const mod = Math.floor((score - 10) / 2);
    return mod >= 0 ? `+${mod}` : mod;
}

const getTagColor = (tag: string) => {
  switch (tag.toLowerCase()) {
    case 'familiar': return 'bg-green-900/50 text-green-300 border-green-700/50';
    case 'constructo': return 'bg-blue-900/50 text-blue-300 border-blue-700/50';
    case 'feérico': return 'bg-pink-900/50 text-pink-300 border-pink-700/50';
    case 'espírito': return 'bg-cyan-900/50 text-cyan-300 border-cyan-700/50';
    case 'guardião': return 'bg-yellow-900/50 text-yellow-300 border-yellow-700/50';
    default: return 'bg-[var(--bg0)] border-[var(--stroke)] text-[var(--muted)]';
  }
};

const TraitBlock: React.FC<{ trait: any }> = ({ trait }) => (
  <div className="border-t border-[var(--stroke)] py-4 first:pt-0 first:border-0">
    <p className="text-sm text-[var(--muted)]">
      <strong className="text-[var(--text)] font-bold italic">{trait.name}{trait.frequency && ` (${trait.frequency})`}.</strong> {trait.text}
    </p>
    {trait.bullets && trait.bullets.length > 0 && (
      <ul className="list-disc list-inside text-sm text-[var(--muted)] mt-2 space-y-1 marker:text-[var(--ember)]">
        {trait.bullets.map((b: string, i: number) => <li key={i}>{b}</li>)}
      </ul>
    )}
  </div>
);

const ActionBlock: React.FC<{ action: any }> = ({ action }) => (
  <div className="border-t border-[var(--stroke)] py-4 first:pt-0 first:border-0">
    <p className="text-sm text-[var(--muted)]">
      <strong className="text-[var(--text)] font-bold italic">{action.name}{action.recharge && ` (${action.recharge})`}.</strong> 
      {action.attack ? (
        <span className="italic"> {action.type}: {action.attack.toHit} para acertar, alcance {action.attack.reach}, {action.attack.targets}. Dano: {action.damage?.map((d: any) => `${d.dice} (${d.avg}) ${d.type}`).join(', ')}.</span>
      ) : action.trigger ? (
        <span className="italic"> {action.trigger}</span>
      ) : ''}
      {' '}{action.effect || (action.effects && typeof action.effects[0] === 'string' ? action.effects[0] : '')}
    </p>
    {action.effects && action.effects.map((effect: any, i: number) => (
      typeof effect !== 'string' && <p key={i} className="text-sm text-[var(--muted)] mt-1"><strong className="text-[var(--text)]">{effect.name}:</strong> {effect.text}</p>
    ))}
  </div>
);

const SpellcastingBlock: React.FC<{ spellcasting: any }> = ({ spellcasting }) => {
  if (!spellcasting || !spellcasting.lists) return null;
  
  const spellsByLevel = new Map<string, string[]>();
  if (spellcasting.lists.atWill) {
    spellsByLevel.set('À Vontade (Truques)', spellcasting.lists.atWill);
  }
  if (spellcasting.lists.perDay) {
    Object.entries(spellcasting.lists.perDay).forEach(([level, spells]) => {
      spellsByLevel.set(`${level}/Dia`, spells as string[]);
    });
  }

  return (
    <div className="border-t border-[var(--stroke)] py-4 first:pt-0 first:border-0">
       <p className="text-sm text-[var(--muted)] italic mb-4">
         A habilidade de conjuração é {spellcasting.ability} (CD {spellcasting.saveDC}, {spellcasting.attackBonus} para acertar).
       </p>
       <div className="overflow-hidden rounded border border-[var(--stroke)]">
         <table className="w-full text-sm">
           <tbody className="divide-y divide-[var(--stroke)]">
             {Array.from(spellsByLevel.entries()).map(([level, spells]) => (
                <tr key={level} className="bg-[var(--bg1)]">
                  <td className="px-4 py-2 font-bold text-[var(--ember)] align-top w-1/3">{level}</td>
                  <td className="px-4 py-2 text-[var(--text)] italic">{spells.join(', ')}</td>
                </tr>
             ))}
           </tbody>
         </table>
       </div>
    </div>
  );
};

const ExpandableDetailRow: React.FC<{ label: string; items?: string[] }> = ({ label, items = [] }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  if (!items || items.length === 0) return null;

  const displayItems = isExpanded ? items : items.slice(0, 4);
  const canExpand = items.length > 4;

  return (
    <div>
      <dt className="font-bold text-[var(--muted)] uppercase tracking-wider">{label}</dt>
      <dd className="text-[var(--text)] flex flex-wrap gap-x-2 items-center">
        <span>{displayItems.join(', ')}</span>
        {canExpand && (
          <button onClick={() => setIsExpanded(!isExpanded)} className="text-xs text-[var(--ember)] hover:underline flex items-center gap-1">
            {isExpanded ? <MinusCircle className="w-3 h-3"/> : <PlusCircle className="w-3 h-3"/>}
            {isExpanded ? 'ver menos' : `+${items.length - 4} mais`}
          </button>
        )}
      </dd>
    </div>
  );
};

const Accordion: React.FC<{ title: string; children: React.ReactNode; defaultOpen?: boolean; id?: string }> = ({ title, children, defaultOpen = false, id }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  return (
    <div id={id} className="border-t border-[var(--ember)]/50 scroll-mt-24 first:border-0">
      <button onClick={() => setIsOpen(!isOpen)} className="w-full flex justify-between items-center p-3 text-[var(--ember)] hover:bg-[var(--ember)]/5 transition-colors">
        <h3 className="font-rpg font-bold text-lg tracking-wider">{title}</h3>
        <ChevronDown className={`w-5 h-5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>
      {isOpen && (
        <div className="px-3 pb-3 animate-in fade-in duration-300">
          {children}
        </div>
      )}
    </div>
  );
};

const JogadorFamiliares: React.FC = () => {
    const [familiarData, setFamiliarData] = useState<FamiliarData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [searchTerm, setSearchTerm] = useState('');
    const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
    const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
    const [activeVariantSlug, setActiveVariantSlug] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'FICHA' | 'MUNDO'>('FICHA');
    
    const [viewMode, setViewMode] = useState<'ficha' | 'glossary'>('ficha');
    const [glossaryKey, setGlossaryKey] = useState<string | null>(null);

    useEffect(() => {
        fetch('/data/familiars.json')
            .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP error: ${res.status}`)))
            .then((data: FamiliarData) => {
                setFamiliarData(data);
                if (data.entries?.length > 0) setSelectedSlug(data.entries[0].slug);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to fetch familiars:", err);
                setError("Não foi possível carregar os familiares.");
                setLoading(false);
            });
    }, []);
    
    const familiars = familiarData?.entries ?? [];
    const typeGlossary = familiarData?.typeGlossary ?? {};

    const filteredData = useMemo(() => {
        let result = [...familiars];
        if (searchTerm) {
            const q = searchTerm.toLowerCase();
            result = result.filter(f => f.name.toLowerCase().includes(q) || f.tags.some(t => t.toLowerCase().includes(q)) || f.creatureType.type.toLowerCase().includes(q));
        }
        result.sort((a, b) => sortOrder === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name));
        return result;
    }, [familiars, searchTerm, sortOrder]);

    const baseFamiliar = useMemo(() => familiars.find(f => f.slug === selectedSlug), [familiars, selectedSlug]);

    const activeFamiliar = useMemo(() => {
        if (!baseFamiliar) return null;
        if (!activeVariantSlug) return baseFamiliar;
    
        const variant = baseFamiliar.variants?.find(v => v.slug === activeVariantSlug);
        if (!variant) return baseFamiliar;
    
        const merged = mergeDeep(JSON.parse(JSON.stringify(baseFamiliar)), variant.overrides);
        if (variant.image) merged.images.portrait = variant.image;
        return merged as Familiar;
    }, [baseFamiliar, activeVariantSlug]);

    const handleSelectFamiliar = (slug: string) => {
        setSelectedSlug(slug);
        setActiveVariantSlug(null);
        setActiveTab('FICHA');
        setViewMode('ficha');
    };
    
    const openGlossary = (key: string) => {
      setGlossaryKey(key);
      setViewMode('glossary');
    };
    
    if (loading) return <div className="flex-1 flex items-center justify-center min-h-[50vh]"><Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" /></div>;
    if (error) return <div className="flex-1 flex flex-col items-center justify-center text-center py-20"><AlertTriangle className="w-10 h-10 text-[var(--flame)] mb-4" /><p>{error}</p></div>;

    const glossaryContent = glossaryKey ? typeGlossary[glossaryKey] : null;

    return (
        <main className="bg-[var(--bg0)] min-h-screen">
            <div className="sticky top-16 md:top-0 z-40 bg-[var(--bg1)]/95 backdrop-blur-md border-b border-[var(--stroke)] p-4">
              <div className="container mx-auto max-w-7xl">
                <div className="mb-4">
                  <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Criaturas & Familiares</h1>
                  <p className="text-[var(--muted)] text-sm">Companheiros, invocações e espíritos vinculados.</p>
                </div>
                <div className="flex flex-col md:flex-row gap-3">
                    <div className="relative flex-grow">
                        <input type="text" placeholder="Buscar criatura, tag, tipo…" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[var(--bg0)] border border-[var(--stroke)] rounded pl-10 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] focus:ring-1 focus:ring-[var(--ember)] outline-none" />
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
                    </div>
                    <div className="flex gap-2 shrink-0">
                        <button onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg0)] border border-[var(--stroke)] rounded text-[var(--muted)] hover:text-[var(--text)] transition-colors text-sm font-medium"><ArrowUpDown className="w-4 h-4" /> {sortOrder === 'asc' ? 'A-Z' : 'Z-A'} </button>
                    </div>
                </div>
              </div>
            </div>
            
            <div className="container mx-auto max-w-7xl px-4 py-8">
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-[384px_1fr] gap-8">
                
                <div className="md:col-span-1 flex flex-col gap-2">
                    {filteredData.map(item => {
                        const isSelected = selectedSlug === item.slug;
                        return (
                            <button key={item.slug} onClick={() => handleSelectFamiliar(item.slug)}
                                className={`w-full text-left p-4 rounded border transition-all duration-200 group flex justify-between items-center ${ isSelected ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_4px_0_0_var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] hover:border-[var(--muted)]' }`}>
                                <div className="flex flex-col gap-1.5 min-w-0">
                                  <span className={`font-bold truncate ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>{item.name}</span>
                                  <span className="text-[11px] text-gray-500 font-mono uppercase tracking-wider">{item.creatureType?.type} • ND {item.combat?.challenge?.cr}</span>
                                  <div className="flex gap-1 mt-1">{item.tags?.slice(0, 3).map(tag => (<span key={tag} className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getTagColor(tag)}`}>{tag}</span>))}</div>
                                </div>
                                {isSelected && <ChevronRight className="w-5 h-5 text-[var(--ember)] shrink-0" />}
                            </button>
                        );
                    })}
                </div>

                <div className="md:col-span-2 lg:col-span-1">
                  {activeFamiliar && baseFamiliar ? (
                    viewMode === 'glossary' && glossaryContent ? (
                      <div className="bg-[var(--bg1)] p-8 rounded border border-[var(--stroke)] animate-in fade-in">
                        <h2 className="font-rpg text-2xl font-bold text-[var(--ember)] mb-4 flex items-center gap-2"><ShieldQuestion className="w-6 h-6"/> O que é: {glossaryContent.title}</h2>
                        <p className="text-[var(--muted)] mb-6 leading-relaxed">{glossaryContent.text}</p>
                        <button onClick={() => setViewMode('ficha')} className="px-6 py-2 bg-[var(--ember)] text-white font-bold rounded text-sm hover:bg-[var(--flame)] transition-colors">Voltar para a ficha</button>
                      </div>
                    ) : (
                    <div className="flex flex-col gap-6 animate-in fade-in">
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div className="lg:col-span-2 flex flex-col gap-4">
                          <div>
                            <h2 className="font-rpg text-4xl font-bold text-[var(--text)]">{activeFamiliar.name}</h2>
                            {activeFamiliar.subtitle && <p className="text-lg text-[var(--muted)] italic -mt-1">{activeFamiliar.subtitle}</p>}
                          </div>
                          <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded p-3 space-y-3">
                              <h3 className="text-xs font-bold uppercase text-[var(--muted)] tracking-wider">Identidade</h3>
                              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                                <div><strong className="text-[var(--muted)] block text-[10px]">ND/PB</strong> <span className="font-mono">{activeFamiliar.combat?.challenge?.cr} / {activeFamiliar.combat?.challenge?.pb}</span></div>
                                <div><strong className="text-[var(--muted)] block text-[10px]">Tamanho</strong> {activeFamiliar.size}</div>
                                <div className="col-span-2"><strong className="text-[var(--muted)] block text-[10px]">Tipo</strong> 
                                  <button onClick={() => openGlossary(activeFamiliar.creatureType?.typeKey)} className={`px-2 py-0.5 rounded border text-xs font-bold transition-colors ${glossaryKey === activeFamiliar.creatureType?.typeKey ? 'bg-[var(--ember)] text-white' : 'bg-[var(--bg2)] text-[var(--text)] hover:border-[var(--ember)]'}`}>{activeFamiliar.creatureType?.type}</button>
                                  {activeFamiliar.creatureType?.subtype && <button onClick={() => openGlossary(activeFamiliar.creatureType?.subtypeKey!)} className={`ml-1 px-2 py-0.5 rounded border text-xs font-bold transition-colors ${glossaryKey === activeFamiliar.creatureType?.subtypeKey ? 'bg-[var(--ember)] text-white' : 'bg-[var(--bg2)] text-[var(--text)] hover:border-[var(--ember)]'}`}>({activeFamiliar.creatureType.subtype})</button>}
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-2 pt-2 border-t border-[var(--stroke)]">{activeFamiliar.tags?.map(t => <span key={t} className={`px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-widest border ${getTagColor(t)}`}>{t}</span>)}</div>
                          </div>
                        </div>
                        <div className="relative aspect-video lg:aspect-square bg-[var(--bg1)] rounded-lg border border-[var(--stroke)] overflow-hidden"><img src={activeFamiliar.images?.portrait} alt={activeFamiliar.name} className="w-full h-full object-cover" /></div>
                      </div>

                      {baseFamiliar.variants && baseFamiliar.variants.length > 0 && (<div className="flex flex-col gap-2 p-3 bg-[var(--bg1)] rounded border border-[var(--stroke)]"> <div className="flex flex-wrap items-center gap-2"> <span className="text-xs font-bold uppercase text-[var(--muted)] mr-2">Formas:</span> <button onClick={() => setActiveVariantSlug(null)} className={`px-3 py-1 text-xs font-bold rounded ${!activeVariantSlug ? 'bg-[var(--ember)] text-white ring-2 ring-offset-2 ring-offset-[var(--bg1)] ring-[var(--ember)]' : 'bg-[var(--bg0)] text-[var(--text)]'}`}>Base</button> {baseFamiliar.variants.map(v => (<button key={v.slug} onClick={() => setActiveVariantSlug(v.slug)} className={`px-3 py-1 text-xs font-bold rounded ${activeVariantSlug === v.slug ? 'bg-[var(--ember)] text-white ring-2 ring-offset-2 ring-offset-[var(--bg1)] ring-[var(--ember)]' : 'bg-[var(--bg0)] text-[var(--text)]'}`}>{v.name}</button>))} </div> <p className="text-[10px] text-center text-[var(--muted)] italic opacity-70 mt-1">Selecionar uma forma altera a ficha e a imagem.</p> </div>)}

                      <div className="border border-[var(--stroke)] bg-[var(--bg1)] rounded p-4">
                        <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-4 pb-4 border-b border-[var(--stroke)]">
                            <div className="flex items-baseline gap-2"><span className="font-rpg text-3xl text-[var(--text)] font-bold">{activeFamiliar.combat?.ac?.value}</span><div><strong className="text-[var(--muted)] block text-xs">CA</strong><span className="text-xs text-[var(--muted)]">({activeFamiliar.combat?.ac?.source})</span></div></div>
                            <div className="flex items-baseline gap-2"><span className="font-rpg text-3xl text-[var(--text)] font-bold">{activeFamiliar.combat?.hp?.average}</span><div><strong className="text-[var(--muted)] block text-xs">PV</strong><span className="text-xs text-[var(--muted)]">({activeFamiliar.combat?.hp?.formula})</span></div></div>
                            <div className="col-span-2 space-y-1"><strong className="text-[var(--muted)] block text-xs">DESLOCAMENTO</strong><div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--text)]">{activeFamiliar.combat?.speeds?.map((s: any) => <span key={s.type}>{s.type} {s.value}</span>)}</div></div>
                        </div>
                         <div className="grid grid-cols-3 lg:grid-cols-6 gap-2 text-center mb-6">
                          {activeFamiliar.combat?.abilities && Object.entries(activeFamiliar.combat.abilities).map(([key, score]) =>(
                            <div key={key} className="bg-[var(--bg0)] p-2 rounded border border-[var(--stroke)]"><div className="font-bold text-xs uppercase text-[var(--muted)]">{key}</div><div className="font-bold text-lg text-[var(--text)]">{score as number}</div><div className="text-xs text-[var(--ember)]">({getAbilityModifier(score as number)})</div></div>
                          ))}
                        </div>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-xs pt-4 border-t border-[var(--stroke)]">
                           <ExpandableDetailRow label="Perícias" items={activeFamiliar.combat?.skills?.map((s: any) => `${s.name} ${s.value}`)} />
                           <ExpandableDetailRow label="Resist. a Dano" items={activeFamiliar.combat?.damage?.resistances} />
                           <ExpandableDetailRow label="Imun. a Dano" items={activeFamiliar.combat?.damage?.immunities} />
                           <ExpandableDetailRow label="Vulnerabilidades" items={activeFamiliar.combat?.damage?.vulnerabilities} />
                           <ExpandableDetailRow label="Imun. a Condições" items={activeFamiliar.combat?.conditions?.immunities} />
                           <ExpandableDetailRow label="Sentidos" items={activeFamiliar.combat?.senses?.map((s: any) => `${s.name} ${s.range}`)} />
                           <div><dt className="font-bold text-[var(--muted)] uppercase tracking-wider">Idiomas</dt><dd className="text-[var(--text)]">{activeFamiliar.combat?.languages?.understands?.join(', ') || 'Nenhum'}{activeFamiliar.combat?.languages?.telepathy ? `, Telepatia ${activeFamiliar.combat.languages.telepathy.range}` : ''}</dd></div>
                           <div><dt className="font-bold text-[var(--muted)] uppercase tracking-wider">Iniciativa</dt><dd className="text-[var(--text)]">{activeFamiliar.combat?.abilities?.dex ? getAbilityModifier(activeFamiliar.combat.abilities.dex) : '+0'}</dd></div>
                        </dl>
                      </div>

                      <div className="flex gap-2 border-b border-[var(--stroke)]"><button onClick={() => setActiveTab('FICHA')} className={`px-4 py-2 text-sm font-bold ${activeTab === 'FICHA' ? 'border-b-2 border-[var(--ember)] text-[var(--text)]' : 'text-[var(--muted)]'}`}>Ficha</button><button onClick={() => setActiveTab('MUNDO')} className={`px-4 py-2 text-sm font-bold ${activeTab === 'MUNDO' ? 'border-b-2 border-[var(--ember)] text-[var(--text)]' : 'text-[var(--muted)]'}`}>Mundo</button></div>

                      {activeTab === 'FICHA' && (
                        <div className="space-y-4">
                           <div className="bg-[var(--bg1)] rounded border border-[var(--stroke)] p-1">
                              {activeFamiliar.traits?.length > 0 && <Accordion id="traits" title="Traços" defaultOpen>{activeFamiliar.traits.map((t: any, i: number) => <TraitBlock key={i} trait={t}/>)}</Accordion>}
                              {activeFamiliar.actions?.length > 0 && <Accordion id="actions" title="Ações" defaultOpen>{activeFamiliar.actions.map((a: any, i: number) => <ActionBlock key={i} action={a}/>)}</Accordion>}
                              {activeFamiliar.bonusActions && activeFamiliar.bonusActions.length > 0 && <Accordion id="bonus-actions" title="Ações Bônus">{activeFamiliar.bonusActions.map((a: any, i: number) => <ActionBlock key={i} action={a}/>)}</Accordion>}
                              {activeFamiliar.reactions && activeFamiliar.reactions.length > 0 && <Accordion id="reactions" title="Reações">{activeFamiliar.reactions.map((a: any, i: number) => <ActionBlock key={i} action={a}/>)}</Accordion>}
                              {activeFamiliar.spellcasting && <Accordion id="spellcasting" title="Conjuração"><SpellcastingBlock spellcasting={activeFamiliar.spellcasting}/></Accordion>}
                           </div>
                        </div>
                      )}
                      {activeTab === 'MUNDO' && ( <div className="space-y-6 text-sm bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]"> <p><strong className="text-[var(--muted)] block text-xs uppercase tracking-wider">Habitat</strong>{activeFamiliar.lore?.habitat}</p> <p><strong className="text-[var(--muted)] block text-xs uppercase tracking-wider">Comportamento</strong>{activeFamiliar.lore?.behavior}</p> <p><strong className="text-[var(--muted)] block text-xs uppercase tracking-wider">Narrativa</strong>{activeFamiliar.lore?.narrative}</p> {activeFamiliar.randomTables && activeFamiliar.randomTables.map((table: any, i: number) => (<div key={i} className="pt-4 border-t border-[var(--stroke)]"><h4 className="font-bold text-[var(--text)] mb-2">{table.name} ({table.roll})</h4><ul className="list-none space-y-1 text-xs">{table.rows.map((row: any, ri: number) => <li key={ri}><strong className="text-[var(--ember)] mr-2">{row.result}</strong>{row.text}</li>)}</ul></div>))}</div>)}

                    </div>
                    )) : ( <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-[var(--muted)] opacity-50 p-8 text-center bg-[var(--bg1)] rounded border border-dashed border-[var(--stroke)]"><Layers className="w-16 h-16 mb-4" /><p className="text-lg font-rpg">Selecione uma criatura na lista para ver a ficha.</p></div> )}
                </div>
              </div>
            </div>
        </main>
    );
};

export default JogadorFamiliares;
