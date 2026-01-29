
import React, { useState, useEffect, useMemo } from 'react';
import { 
  Search, 
  BookOpen, 
  Loader2, 
  AlertTriangle, 
  Volume2, 
  Languages, 
  Feather, 
  ArrowRight,
  Copy,
  Check,
  Globe,
  Mic,
  Play,
  Hand,
  Hash,
  Keyboard,
  Info,
  Layers,
  ChevronDown
} from 'lucide-react';
import { Language, Glyph, BasicSign } from '../types';
import { transliterateText, translateText, speakText } from '../lib/language-engine';

// --- COMPONENTS ---

const AudioPlayer: React.FC<{ text: string, langRef: string, label?: string }> = ({ text, langRef, label }) => (
  <button 
    onClick={() => speakText(text, langRef)}
    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--bg2)] border border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-all text-xs font-bold"
    title="Ouvir pronúncia (IA TTS)"
  >
    <Volume2 className="w-3 h-3" />
    {label || "Ouvir"}
  </button>
);

const TranslatorPlayground: React.FC<{ languages: Language[] }> = ({ languages }) => {
  const [inputText, setInputText] = useState('');
  const [targetLangSlug, setTargetLangSlug] = useState('comum');
  const [activeOutput, setActiveOutput] = useState<'rom' | 'nat' | 'braille' | 'gloss'>('rom');
  const [copied, setCopied] = useState<string | null>(null);

  const targetLang = languages.find(l => l.slug === targetLangSlug) || languages[0];

  const translated = useMemo(() => translateText(inputText, targetLang), [inputText, targetLang]);
  const native = useMemo(() => transliterateText(translated, targetLang.transliterationEngine), [translated, targetLang]);
  const braille = useMemo(() => transliterateText(translated, 'braille'), [translated]);

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const isSigned = targetLang.modality === 'signed';

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

        <div className="flex flex-col gap-4">
          <div className="flex gap-1 border-b border-[var(--stroke)] overflow-x-auto">
             <button onClick={() => setActiveOutput('rom')} className={`px-3 py-2 text-[10px] uppercase font-bold border-b-2 transition-all ${activeOutput === 'rom' ? 'border-[var(--ember)] text-[var(--text)]' : 'border-transparent text-[var(--muted)]'}`}>Romanização</button>
             {!isSigned && <button onClick={() => setActiveOutput('nat')} className={`px-3 py-2 text-[10px] uppercase font-bold border-b-2 transition-all ${activeOutput === 'nat' ? 'border-[var(--ember)] text-[var(--text)]' : 'border-transparent text-[var(--muted)]'}`}>Nativo</button>}
             <button onClick={() => setActiveOutput('braille')} className={`px-3 py-2 text-[10px] uppercase font-bold border-b-2 transition-all ${activeOutput === 'braille' ? 'border-[var(--ember)] text-[var(--text)]' : 'border-transparent text-[var(--muted)]'}`}>Braile</button>
             {isSigned && <button onClick={() => setActiveOutput('gloss')} className={`px-3 py-2 text-[10px] uppercase font-bold border-b-2 transition-all ${activeOutput === 'gloss' ? 'border-[var(--ember)] text-[var(--text)]' : 'border-transparent text-[var(--muted)]'}`}>Glosa</button>}
          </div>

          <div className="bg-[var(--bg2)] border border-[var(--stroke)] rounded p-4 flex-1 flex flex-col justify-center items-center relative group min-h-[120px]">
             <p className={`text-center break-words w-full px-4 text-[var(--text)] ${activeOutput === 'nat' ? 'text-3xl text-[var(--ember)] font-serif' : activeOutput === 'braille' ? 'text-4xl' : 'text-xl font-medium'}`}>
               {activeOutput === 'rom' ? (translated || "...") : activeOutput === 'nat' ? (native || "...") : activeOutput === 'braille' ? (braille || "...") : (translated || "...")}
             </p>
             
             <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {!isSigned && <button onClick={() => speakText(translated, targetLang.referenceLanguage)} className="p-1.5 rounded hover:bg-[var(--bg0)] text-[var(--muted)] hover:text-[var(--text)]"><Volume2 className="w-4 h-4" /></button>}
                <button onClick={() => handleCopy(activeOutput === 'rom' ? translated : activeOutput === 'nat' ? native : braille, 'main')} className="p-1.5 rounded hover:bg-[var(--bg0)] text-[var(--muted)] hover:text-[var(--text)]">{copied === 'main' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}</button>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// --- ACCESSIBILITY TAB ---

const AccessibilityTab: React.FC<{ lang: Language }> = ({ lang }) => {
  const [showBraille, setShowBraille] = useState(false);

  if (lang.modality === 'signed') {
    return (
      <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
        <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
          <h3 className="font-rpg text-xl font-bold text-[var(--ember)] mb-4 flex items-center gap-2">
            <Hand className="w-5 h-5" /> Alfabeto Manual (Datilologia)
          </h3>
          <div className="grid grid-cols-4 sm:grid-cols-7 gap-4">
            {Object.entries(lang.accessibility?.manualAlphabet || {}).map(([letter, icon]) => (
              <div key={letter} className="flex flex-col items-center p-3 rounded bg-[var(--bg2)] border border-[var(--stroke)]">
                <span className="text-3xl mb-1">{icon}</span>
                <span className="text-xs font-bold text-[var(--muted)]">{letter}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-4">Sinais Básicos</h3>
          <div className="grid sm:grid-cols-2 gap-4">
            {lang.accessibility?.basicSigns?.map(sign => (
              <div key={sign.slug} className="p-4 rounded bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] transition-colors">
                <h4 className="font-bold text-[var(--ember)] mb-1">{sign.label}</h4>
                <p className="text-xs text-[var(--muted)]">{sign.description}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2">
      <div className="flex items-center justify-between p-4 bg-[var(--bg1)] rounded border border-[var(--stroke)]">
        <div>
          <h3 className="font-bold text-[var(--text)]">Suporte a Braile</h3>
          <p className="text-xs text-[var(--muted)]">Este idioma possui transcrição completa para o sistema tátil.</p>
        </div>
        <button 
          onClick={() => setShowBraille(!showBraille)}
          className={`px-4 py-2 rounded text-xs font-bold transition-all ${showBraille ? 'bg-[var(--ember)] text-white' : 'bg-[var(--bg0)] border border-[var(--stroke)] text-[var(--muted)]'}`}
        >
          {showBraille ? 'Esconder Braile' : 'Ver em Braile'}
        </button>
      </div>

      {showBraille && (
        <div className="p-6 bg-[var(--bg1)] rounded border border-[var(--stroke)] animate-in zoom-in-95">
          <h4 className="text-[10px] uppercase font-bold text-[var(--muted)] mb-4">Amostra em Braile ({lang.name})</h4>
          <div className="space-y-4">
            <div>
               <p className="text-[10px] text-[var(--muted)]">Nome Nativo:</p>
               <p className="text-4xl text-[var(--text)] mt-1">{transliterateText(lang.nativeName, 'braille')}</p>
            </div>
            {lang.phrases?.slice(0, 2).map((p, i) => (
              <div key={i}>
                <p className="text-[10px] text-[var(--muted)]">{p.pt}:</p>
                <p className="text-4xl text-[var(--text)] mt-1">{transliterateText(p.native, 'braille')}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="p-4 bg-[var(--bg2)]/30 border border-dashed border-[var(--stroke)] rounded text-center">
        <p className="text-xs text-[var(--muted)]">Para outros recursos de acessibilidade, consulte o Grão-Escriba no Discord.</p>
      </div>
    </div>
  );
};

// --- MAIN PAGE ---

const JogadorIdiomas: React.FC = () => {
  const [languages, setLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'writing' | 'phrases' | 'access' | 'translator'>('overview');
  const [searchTerm, setSearchTerm] = useState('');
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

  const categorizedLanguages = useMemo(() => {
    const list = languages.filter(l => 
      l.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      l.peoples.some(p => p.toLowerCase().includes(searchTerm.toLowerCase()))
    );

    return {
      idiomas: list.filter(l => l.modality === 'spoken' || l.modality === 'signed'),
      escrita: list.filter(l => l.modality === 'script')
    };
  }, [languages, searchTerm]);

  const handleSelect = (slug: string) => {
    setSelectedSlug(slug);
    setActiveTab('overview');
    if (window.innerWidth < 768) setIsMobileDetailOpen(true);
  };

  if (loading) return (
    <div className="flex-1 flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <Loader2 className="w-8 h-8 text-[var(--ember)] animate-spin" />
      <p className="text-[var(--muted)]">Decifrando runas com IA...</p>
    </div>
  );

  return (
    <main className="min-h-screen bg-[var(--bg0)] flex flex-col">
      <div className="flex-none bg-[var(--bg1)] border-b border-[var(--stroke)] p-4 z-20 sticky top-16 md:static">
        <div className="container mx-auto max-w-7xl">
          <h1 className="font-rpg text-3xl font-bold text-[var(--text)] mb-1">Idiomas & Sistemas</h1>
          <p className="text-[var(--muted)] text-sm">Voz, sinais e sistemas de escrita tátil.</p>
        </div>
      </div>

      <div className="container mx-auto max-w-7xl md:px-4 flex flex-col md:flex-row gap-8 relative mt-4 md:mt-8">
        
        {/* --- LISTA (Sidebar) --- */}
        <div className={`
          md:w-80 shrink-0 flex flex-col gap-6
          ${isMobileDetailOpen ? 'hidden md:flex' : 'flex'}
          md:sticky md:top-24 md:self-start md:max-h-[calc(100vh-8rem)]
        `}>
          <div className="relative">
            <input 
              type="text" 
              placeholder="Buscar..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-[var(--bg1)] border border-[var(--stroke)] rounded pl-9 pr-4 py-2 text-[var(--text)] text-sm focus:border-[var(--ember)] outline-none"
            />
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-[var(--muted)]" />
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-6 pr-1">
            
            {/* Seção Idiomas */}
            <div>
               <h3 className="text-[10px] font-bold uppercase text-[var(--muted)] tracking-[0.2em] mb-3 px-2 flex items-center gap-2">
                 <Mic className="w-3 h-3" /> Idiomas
               </h3>
               <div className="space-y-1">
                {categorizedLanguages.idiomas.map(l => {
                  const isSelected = selectedSlug === l.slug;
                  return (
                    <button key={l.slug} onClick={() => handleSelect(l.slug)} className={`w-full text-left px-4 py-3 rounded border transition-all duration-200 group flex flex-col gap-1 ${isSelected ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] hover:bg-[var(--bg2)]'}`}>
                      <div className="flex justify-between items-center w-full">
                        <span className={`text-sm font-bold ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>{l.name}</span>
                        {l.modality === 'signed' && <span className="text-[8px] px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-300 border border-purple-700 font-bold">SINAIS</span>}
                      </div>
                    </button>
                  );
                })}
               </div>
            </div>

            {/* Seção Escrita */}
            <div>
               <h3 className="text-[10px] font-bold uppercase text-[var(--muted)] tracking-[0.2em] mb-3 px-2 flex items-center gap-2">
                 <Feather className="w-3 h-3" /> Sistemas de Escrita
               </h3>
               <div className="space-y-1">
                {categorizedLanguages.escrita.map(l => {
                  const isSelected = selectedSlug === l.slug;
                  return (
                    <button key={l.slug} onClick={() => handleSelect(l.slug)} className={`w-full text-left px-4 py-3 rounded border transition-all duration-200 group flex flex-col gap-1 ${isSelected ? 'bg-[var(--bg2)] border-[var(--ember)] shadow-[inset_3px_0_0_var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] hover:bg-[var(--bg2)]'}`}>
                      <div className="flex justify-between items-center w-full">
                        <span className={`text-sm font-bold ${isSelected ? 'text-[var(--text)]' : 'text-[var(--muted)] group-hover:text-[var(--text)]'}`}>{l.name}</span>
                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-300 border border-blue-700 font-bold">TÁTIL</span>
                      </div>
                    </button>
                  );
                })}
               </div>
            </div>
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

          <div className="mb-6 flex justify-end">
             <button 
               onClick={() => { setActiveTab('translator'); if(window.innerWidth < 768) setIsMobileDetailOpen(true); }}
               className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-bold transition-all ${activeTab === 'translator' ? 'bg-[var(--ember)] text-white border-[var(--ember)]' : 'bg-[var(--bg1)] border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)]'}`}
             >
               <Mic className="w-4 h-4" />
               Abrir Tradutor Arcano
             </button>
          </div>

          {activeTab === 'translator' ? (
            <TranslatorPlayground languages={languages} />
          ) : activeLang ? (
            <div className="flex flex-col gap-6 animate-in fade-in duration-300">
              
              <div className="border-b border-[var(--stroke)] pb-6">
                <div className="flex flex-wrap gap-2 mb-3">
                  {activeLang.peoples.map(p => (
                    <span key={p} className="px-2 py-1 rounded bg-[var(--bg2)] text-[10px] font-bold uppercase text-[var(--muted)] border border-[var(--stroke)]">
                      {p}
                    </span>
                  ))}
                  <span className="px-2 py-1 rounded bg-[var(--bg2)] text-[10px] font-bold uppercase text-[var(--ember)] border border-[var(--ember)]/30">
                    {activeLang.status}
                  </span>
                </div>
                <h1 className="font-rpg text-4xl lg:text-5xl font-bold text-[var(--text)] mb-2 flex items-baseline gap-3">
                  {activeLang.name}
                  <span className="text-xl text-[var(--muted)] font-serif italic font-normal opacity-70">
                    "{activeLang.nativeName}"
                  </span>
                </h1>
                
                <div className="flex items-center gap-4 mt-4">
                   {activeLang.modality !== 'signed' && <AudioPlayer text={activeLang.nativeName} langRef={activeLang.referenceLanguage} label="Ouvir Nome" />}
                   <span className="text-sm text-[var(--muted)] flex items-center gap-2">
                     <Feather className="w-4 h-4" /> Escrita: <strong className="text-[var(--text)]">{activeLang.writingSystem.name}</strong>
                   </span>
                </div>
              </div>

              <div className="flex gap-1 border-b border-[var(--stroke)] overflow-x-auto">
                {[
                  { id: 'overview', label: 'Visão Geral' },
                  { id: 'writing', label: 'Escrita & Alfabeto' },
                  { id: 'phrases', label: 'Frases Úteis' },
                  { id: 'access', label: 'Acessibilidade' },
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
                        <Volume2 className="w-4 h-4 text-[var(--ember)]" /> Pronúncia & Variações
                      </h3>
                      {activeLang.pronunciationTips ? (
                        <ul className="list-disc list-inside space-y-1 text-sm text-[var(--muted)]">
                          {activeLang.pronunciationTips.map((tip, i) => <li key={i}>{tip}</li>)}
                        </ul>
                      ) : (
                        <p className="text-sm text-[var(--muted)] italic">Uso de sinais ou sistema tátil para comunicação.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'writing' && (
                <div className="animate-in fade-in slide-in-from-bottom-2">
                  <div className="mb-6 p-4 bg-[var(--bg1)] border border-[var(--stroke)] rounded text-sm text-[var(--muted)] flex justify-between items-center">
                    <span>
                      <strong className="text-[var(--text)]">Sistema:</strong> {activeLang.writingSystem.type} ({activeLang.writingSystem.direction.toUpperCase()})
                    </span>
                  </div>
                  {activeLang.glyphs ? (
                    <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-3">
                      {activeLang.glyphs.map((g, i) => (
                        <div key={i} className="flex flex-col items-center p-3 rounded bg-[var(--bg2)] border border-[var(--stroke)] hover:border-[var(--ember)] transition-colors">
                          <span className={`text-3xl font-serif text-[var(--text)] mb-2 ${activeLang.transliterationEngine === 'braille' ? 'text-4xl' : ''}`}>{g.char}</span>
                          <span className="text-xs font-bold text-[var(--muted)] uppercase">{g.translit}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-12 text-center border border-dashed border-[var(--stroke)] rounded text-[var(--muted)]">
                      Este idioma utiliza modalidade sinalizada ou não possui alfabeto registrado.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'phrases' && (
                <div className="animate-in fade-in slide-in-from-bottom-2">
                  {activeLang.phrases && activeLang.phrases.length > 0 ? (
                    <div className="overflow-hidden rounded border border-[var(--stroke)]">
                      <table className="w-full text-left text-sm">
                        <thead className="bg-[var(--bg2)] text-[var(--ember)] font-bold uppercase text-xs">
                          <tr>
                            <th className="p-4">Frase (Comum)</th>
                            <th className="p-4">Nativo / Romanizado</th>
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
                              <td className="p-4">
                                {activeLang.modality !== 'signed' && (
                                  <button onClick={() => speakText(phrase.native, activeLang.referenceLanguage)} className="p-2 rounded-full hover:bg-[var(--bg2)] text-[var(--muted)] hover:text-[var(--ember)]">
                                    <Play className="w-4 h-4 fill-current" />
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="py-12 text-center border border-dashed border-[var(--stroke)] rounded text-[var(--muted)]">
                      Nenhuma frase comum registrada.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'access' && (
                <AccessibilityTab lang={activeLang} />
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
