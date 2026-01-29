
import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, 
  Filter, 
  BookOpen, 
  Loader2, 
  AlertTriangle, 
  X, 
  Volume2, 
  Languages, 
  Feather, 
  ArrowRight,
  Copy,
  Check,
  Globe,
  Mic,
  Play
} from 'lucide-react';
import { Language, Glyph } from '../../types';
import { transliterateText, translateText, speakText } from '../lib/language-engine';

// --- COMPONENTS ---

const AudioPlayer: React.FC<{ text: string, langRef: string, label?: string }> = ({ text, langRef, label }) => (
  <button 
    onClick={() => speakText(text, langRef)}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg2)] border border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-all text-xs font-bold"
    title="Ouvir pronúncia (TTS)"
  >
    <Volume2 className="w-3 h-3" />
    {label || "Ouvir"}
  </button>
);

const TranslatorPlayground: React.FC<{ languages: Language[] }> = ({ languages }) => {
  const [inputText, setInputText] = useState('');
  const [targetLangSlug, setTargetLangSlug] = useState('enanico');
  const [copied, setCopied] = useState<string | null>(null);

  const targetLang = languages.find(l => l.slug === targetLangSlug) || languages[0];

  const translated = useMemo(() => translateText(inputText, targetLang), [inputText, targetLang]);
  const transliterated = useMemo(() => transliterateText(translated, targetLang.transliterationEngine), [translated, targetLang]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="bg-[var(--bg1)] border border-[var(--stroke)] rounded-lg p-6 animate-in fade-in slide-in-from-bottom-4 duration-500 shadow-xl">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <h3 className="font-rpg text-xl font-bold text-[var(--text)] flex items-center gap-2">
          <Languages className="w-5 h-5 text-[var(--ember)]" />
          Tradutor Arcano (BETA)
        </h3>
        <select 
          value={targetLangSlug}
          onChange={(e) => setTargetLangSlug(e.target.value)}
          className="bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--text)] rounded px-3 py-2 text-sm font-bold focus:border-[var(--ember)] outline-none"
        >
          {languages.map(l => (
            <option key={l.slug} value={l.slug}>{l.name}</option>
          ))}
        </select>
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        {/* Input */}
        <div className="flex flex-col gap-2">
          <label className="text-[10px] uppercase font-bold text-[var(--muted)] tracking-wider">Comum (Português)</label>
          <textarea 
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Digite algo para traduzir..."
            className="w-full h-32 bg-[var(--bg0)] border border-[var(--stroke)] rounded p-4 text-[var(--text)] focus:border-[var(--ember)] outline-none resize-none transition-colors"
          />
          <div className="flex justify-end">
             <button onClick={() => setInputText('')} className="text-xs text-[var(--muted)] hover:text-[var(--flame)]">Limpar</button>
          </div>
        </div>

        {/* Output */}
        <div className="flex flex-col gap-4">
          
          {/* Romanized Output */}
          <div className="bg-[var(--bg0)]/50 border border-[var(--stroke)] rounded p-3 relative group">
             <span className="text-[10px] uppercase font-bold text-[var(--muted)] tracking-wider block mb-1">Tradução (Romanizada)</span>
             <p className="text-[var(--text)] font-medium min-h-[1.5em]">{translated || "..."}</p>
             
             <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button 
                  onClick={() => speakText(translated, targetLang.referenceLanguage)} 
                  className="p-1.5 rounded hover:bg-[var(--bg2)] text-[var(--muted)] hover:text-[var(--text)]"
                  title="Ouvir"
                >
                  <Volume2 className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => handleCopy(translated, 'rom')} 
                  className="p-1.5 rounded hover:bg-[var(--bg2)] text-[var(--muted)] hover:text-[var(--text)]"
                  title="Copiar"
                >
                  {copied === 'rom' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                </button>
             </div>
          </div>

          {/* Native Output */}
          <div className="bg-[var(--bg2)] border border-[var(--stroke)] rounded p-4 flex-1 flex flex-col justify-center items-center relative group min-h-[120px]">
             <span className="absolute top-2 left-3 text-[10px] uppercase font-bold text-[var(--muted)] tracking-wider">Escrita Nativa ({targetLang.writingSystem.name})</span>
             <p className="text-2xl md:text-3xl text-[var(--ember)] text-center break-words w-full px-4 font-serif">
               {transliterated || "..."}
             </p>
             
             <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button 
                  onClick={() => handleCopy(transliterated, 'nat')} 
                  className="flex items-center gap-2 px-3 py-1 rounded bg-[var(--bg0)] border border-[var(--stroke)] text-xs font-bold text-[var(--text)] hover:border-[var(--ember)]"
                >
                  {copied === 'nat' ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                  Copiar
                </button>
             </div>
          </div>

        </div>
      </div>
      
      <p className="mt-4 text-[10px] text-[var(--muted)] text-center opacity-60">
        * A tradução é uma aproximação baseada em dicionário parcial e regras fonéticas. Use para imersão, não para tratados legais.
      </p>
    </div>
  );
};

// --- MAIN COMPONENT ---

const JogadorIdiomas: React.FC = () => {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'writing' | 'phrases' | 'translator'>('overview');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Mobile
  const [isMobileDetailOpen, setIsMobileDetailOpen] = useState(false);

  useEffect(() => {
    fetch('/data/languages.json')
      .then(res => res.json())
      .then(data => {
        setLanguages(data);
        setLoading(false);
        if (data.length > 0) setSelectedSlug(data[0].slug);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const activeLang = useMemo(() => languages.find(l => l.slug === selectedSlug), [languages, selectedSlug]);

  const filteredLanguages = useMemo(() => {
    return languages.filter(l => 
      l.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.nativeName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.peoples.some(p => p.toLowerCase().includes(searchTerm.toLowerCase()))
    );
  }, [languages, searchTerm]);

  const handleSelect = (slug: string) => {
    setSelectedSlug(slug);
    setActiveTab('overview');
    if (window.innerWidth < 768) setIsMobileDetailOpen(true);
  };

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Decifrando runas...</p>
    </div>
  );

  return (
    <main className="min-h-screen bg-[var(--bg0)] flex flex-col">
      
      {/* Header */}
      <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20 sticky top-16 md:static">
        <div className="container mx-auto max-w-7xl">
          <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Idiomas de Cinéria</h1>
          <p className="text-[var(--muted)] text-sm">Enciclopédia de línguas, dialetos e alfabetos.</p>
        </div>
      </div>

      <div className="container mx-auto max-w-7xl md:px-4 flex flex-col md:flex-row gap-8 relative mt-4 md:mt-8">
        
        {/* --- LISTA (Sidebar) --- */}
        <div className={`
          md:w-80 shrink-0 flex flex-col gap-4
          ${isMobileDetailOpen ? 'hidden md:flex' : 'flex'}
          md:sticky md:top-24 md:self-start md:max-h-[calc(100vh-8rem)]
        `}>
          <div className="relative">
            <input 
              type="text" 
              placeholder="Buscar idioma..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[var(--bg1)] border border-[var(--stroke)] rounded pl-9 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] outline-none"
            />
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
            {filteredLanguages.map(l => {
              const isSelected = selectedSlug === l.slug;
              return (
                <button
                  key={l.slug}
                  onClick={() => handleSelect(l.slug)}
                  className={`w-full text-left px-4 py-3 rounded border transition-all duration-200 group flex flex-col gap-1.5 ${
                    isSelected 
                      ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' 
                      : 'bg-[var(--bg1)] border-[var(--stroke)] hover:bg-[var(--bg2)]'
                  }`}
                >
                  <div className="flex justify-between items-center w-full">
                    <span className={`text-sm font-bold ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>
                      {l.name}
                    </span>
                    <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                      l.category === 'Comum' ? 'border-green-800 text-green-400' :
                      l.category === 'Regional' ? 'border-blue-800 text-blue-400' :
                      l.category === 'Exótico' ? 'border-purple-800 text-purple-400' :
                      'border-red-800 text-red-400'
                    }`}>
                      {l.category}
                    </span>
                  </div>
                  <span className="text-xs text-[var(--muted)] opacity-60 font-serif italic">
                    {l.nativeName}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* --- DETALHE --- */}
        <div className={`
          flex-1 min-w-0
          ${isMobileDetailOpen ? 'block' : 'hidden md:block'}
        `}>
          
          {/* Mobile Back */}
          <div className="md:hidden mb-4 flex items-center gap-2">
             <button onClick={() => setIsMobileDetailOpen(false)} className="text-[var(--text)] p-2 -ml-2 bg-[var(--bg1)] rounded-full border border-[var(--stroke)]">
               <ArrowRight className="w-5 h-5 rotate-180" />
             </button>
             <span className="font-bold text-[var(--text)]">Voltar</span>
          </div>

          {/* Tradutor Global Tab */}
          <div className="mb-6 flex justify-end">
             <button 
               onClick={() => { setActiveTab('translator'); if(window.innerWidth < 768) setIsMobileDetailOpen(true); }}
               className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-bold transition-all ${activeTab === 'translator' ? 'bg-[var(--ember)] text-white border-[var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)]'}`}
             >
               <Mic className="w-4 h-4" />
               Abrir Tradutor
             </button>
          </div>

          {activeTab === 'translator' ? (
            <TranslatorPlayground languages={languages} />
          ) : activeLang ? (
            <div className="flex flex-col gap-6 animate-in fade-in duration-300">
              
              {/* Header */}
              <div className="border-b border-[var(--stroke)] pb-6">
                <div className="flex flex-wrap gap-2 mb-3">
                  {activeLang.peoples.map(p => (
                    <span key={p} className="px-2 py-1 rounded bg-[var(--bg2)] text-[10px] font-bold uppercase text-[var(--muted)] border border-[var(--stroke)]">
                      {p}
                    </span>
                  ))}
                </div>
                <h1 className="font-rpg text-4xl lg:text-5xl font-bold text-[var(--text)] mb-2 flex items-baseline gap-3">
                  {activeLang.name}
                  <span className="text-xl text-[var(--muted)] font-serif italic font-normal opacity-70">
                    "{activeLang.nativeName}"
                  </span>
                </h1>
                
                <div className="flex items-center gap-4 mt-4">
                   <AudioPlayer text={activeLang.nativeName} langRef={activeLang.referenceLanguage} label="Ouvir Nome" />
                   <span className="text-sm text-[var(--muted)] flex items-center gap-2">
                     <Feather className="w-4 h-4" /> Escrita: <strong className="text-[var(--text)]">{activeLang.writingSystem.name}</strong>
                   </span>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-1 border-b border-[var(--stroke)] overflow-x-auto">
                {[
                  { id: 'overview', label: 'Visão Geral' },
                  { id: 'writing', label: 'Escrita & Alfabeto' },
                  { id: 'phrases', label: 'Frases Úteis' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`px-6 py-3 text-sm font-bold uppercase tracking-wide border-b-2 transition-colors whitespace-nowrap ${
                      activeTab === tab.id 
                        ? 'border-[var(--ember)] text-[var(--text)] bg-[var(--bg1)] rounded-t' 
                        : 'border-transparent text-[var(--muted)] hover:text-[var(--text)]'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Content: Overview */}
              {activeTab === 'overview' && (
                <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
                  <div className="prose prose-invert max-w-none text-[var(--muted)] leading-relaxed">
                    {activeLang.description.map((p, i) => <p key={i}>{p}</p>)}
                  </div>

                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)]">
                      <h3 className="font-rpg text-lg font-bold text-[var(--text)] mb-3 flex items-center gap-2">
                        <Globe className="w-4 h-4 text-[var(--ember)]" /> Regiões
                      </h3>
                      <ul className="list-disc list-inside space-y-1 text-sm text-[var(--muted)]">
                        {activeLang.regions.map(r => <li key={r}>{r}</li>)}
                      </ul>
                    </div>
                    <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)]">
                      <h3 className="font-rpg text-lg font-bold text-[var(--text)] mb-3 flex items-center gap-2">
                        <Volume2 className="w-4 h-4 text-[var(--ember)]" /> Dicas de Pronúncia
                      </h3>
                      {activeLang.pronunciationTips ? (
                        <ul className="list-disc list-inside space-y-1 text-sm text-[var(--muted)]">
                          {activeLang.pronunciationTips.map((tip, i) => <li key={i}>{tip}</li>)}
                        </ul>
                      ) : (
                        <p className="text-sm text-[var(--muted)] italic">Nenhuma dica específica registrada.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Content: Writing */}
              {activeTab === 'writing' && (
                <div className="animate-in fade-in slide-in-from-bottom-2">
                  <div className="mb-6 p-4 bg-[var(--bg1)] border border-[var(--stroke)] rounded text-sm text-[var(--muted)] flex justify-between items-center">
                    <span>
                      <strong className="text-[var(--text)]">Sistema:</strong> {activeLang.writingSystem.type} ({activeLang.writingSystem.direction.toUpperCase()})
                      {activeLang.writingSystem.notes && <span className="block mt-1 opacity-80">{activeLang.writingSystem.notes}</span>}
                    </span>
                  </div>

                  {activeLang.glyphs ? (
                    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3">
                      {activeLang.glyphs.map((g, i) => (
                        <div key={i} className="flex flex-col items-center p-3 rounded bg-[var(--bg2)] border border-[var(--stroke)] hover:border-[var(--ember)] transition-colors">
                          <span className="text-3xl font-serif text-[var(--text)] mb-2">{g.char}</span>
                          <span className="text-xs font-bold text-[var(--muted)] uppercase">{g.translit}</span>
                          {g.notes && <span className="text-[9px] text-[var(--muted)] opacity-50 mt-1">{g.notes}</span>}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-12 text-center border border-dashed border-[var(--stroke)] rounded text-[var(--muted)]">
                      Este idioma não possui um alfabeto registrado ou utiliza escrita variável.
                    </div>
                  )}
                </div>
              )}

              {/* Content: Phrases */}
              {activeTab === 'phrases' && (
                <div className="animate-in fade-in slide-in-from-bottom-2">
                  {activeLang.phrases && activeLang.phrases.length > 0 ? (
                    <div className="overflow-hidden rounded border border-[var(--stroke)]">
                      <table className="w-full text-left text-sm">
                        <thead className="bg-[var(--bg2)] text-[var(--ember)] font-bold uppercase text-xs">
                          <tr>
                            <th className="p-4">Frase (Comum)</th>
                            <th className="p-4">Nativo</th>
                            <th className="p-4 hidden sm:table-cell">Uso</th>
                            <th className="p-4 w-10"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--stroke)] bg-[var(--bg1)]">
                          {activeLang.phrases.map((phrase, i) => (
                            <tr key={i} className="hover:bg-[var(--bg0)] transition-colors">
                              <td className="p-4 font-medium text-[var(--text)]">{phrase.pt}</td>
                              <td className="p-4">
                                <span className="block text-lg font-serif text-[var(--text)] mb-1">{phrase.native}</span>
                                <span className="text-xs text-[var(--muted)] italic">{phrase.translit}</span>
                              </td>
                              <td className="p-4 text-[var(--muted)] hidden sm:table-cell">{phrase.usage}</td>
                              <td className="p-4">
                                <button 
                                  onClick={() => speakText(phrase.native, activeLang.referenceLanguage)}
                                  className="p-2 rounded-full hover:bg-[var(--bg2)] text-[var(--muted)] hover:text-[var(--ember)]"
                                >
                                  <Play className="w-4 h-4 fill-current" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="py-12 text-center border border-dashed border-[var(--stroke)] rounded text-[var(--muted)]">
                      Nenhuma frase comum registrada para este idioma.
                    </div>
                  )}
                </div>
              )}

            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-[var(--muted)] opacity-50 py-20">
              <BookOpen className="w-16 h-16 mb-4" />
              <p>Selecione um idioma para estudar.</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
};

export default JogadorIdiomas;
