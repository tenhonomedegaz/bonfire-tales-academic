
import React from 'react';
import { Link } from 'react-router-dom';
import { HomeData } from '../types';
import LiveNowCard from '../components/LiveNowCard';
import { 
  PlayCircle, 
  Map as MapIcon, 
  BookOpen, 
  ScrollText, 
  ArrowRight, 
  Sparkles, 
  Twitter, 
  Youtube, 
  Instagram, 
  Video, 
  Disc, 
  ExternalLink,
  Globe,
  Clock,
  Accessibility
} from 'lucide-react';

interface HomeProps {
  data: HomeData;
}

const Section: React.FC<{ 
  children: React.ReactNode; 
  className?: string; 
  id?: string;
  darker?: boolean;
}> = ({ children, className = "", id, darker = false }) => (
  <section id={id} className={`py-20 md:py-28 relative ${darker ? 'bg-[var(--bg0)]' : 'bg-[var(--bg1)]'} ${className}`}>
    <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-[var(--stroke)] to-transparent opacity-50" />
    <div className="container mx-auto px-4 relative z-10">
      {children}
    </div>
  </section>
);

const getSocialIcon = (iconId?: string) => {
  switch (iconId) {
    case 'discord': return <Disc className="w-5 h-5" />;
    case 'twitter': return <Twitter className="w-5 h-5" />;
    case 'youtube': return <Youtube className="w-5 h-5" />;
    case 'instagram': return <Instagram className="w-5 h-5" />;
    case 'tiktok': return <Video className="w-5 h-5" />;
    default: return <ExternalLink className="w-5 h-5" />;
  }
};

const getFeatureIcon = (iconId: string) => {
  switch (iconId) {
    case 'globe': return <Globe className="w-8 h-8 text-[var(--ember)]" />;
    case 'clock': return <Clock className="w-8 h-8 text-[var(--ember)]" />;
    case 'accessibility': return <Accessibility className="w-8 h-8 text-[var(--ember)]" />;
    default: return <Sparkles className="w-8 h-8 text-[var(--ember)]" />;
  }
};

const Home: React.FC<HomeProps> = ({ data }) => {
  return (
    <main className="flex-1 overflow-x-hidden">
      
      {/* 1. HERO + CTAs */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        <div className="absolute inset-0 z-0 bg-[var(--bg0)]">
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] rounded-full bg-[var(--flame)] opacity-[0.08] blur-[120px]"></div>
           <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-[var(--bg0)] to-transparent"></div>
        </div>

        <div className="relative z-10 container mx-auto px-4 text-center max-w-5xl flex flex-col items-center">
          <div className="mb-6 inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-[var(--stroke)] bg-black/40 backdrop-blur text-xs font-bold uppercase tracking-widest text-[var(--ember)] animate-fade-in-up">
            <Sparkles className="w-3 h-3" />
            <span>Open Beta v0.9</span>
          </div>
          
          <h1 className="font-rpg text-5xl md:text-7xl lg:text-8xl font-bold text-[var(--text)] mb-8 leading-[1.1] tracking-tight drop-shadow-2xl">
            {data.hero.headline}
          </h1>
          
          <p className="text-lg md:text-xl text-[var(--muted)] mb-12 max-w-2xl mx-auto leading-relaxed">
            {data.hero.subhead}
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 w-full sm:w-auto">
            <a 
              href={data.hero.ctaPrimary.href}
              className="w-full sm:w-auto px-10 py-4 rounded-sm bg-[var(--flame)] hover:bg-[var(--ember)] text-white font-rpg font-bold text-lg tracking-wide transition-all shadow-[0_0_30px_rgba(210,23,23,0.3)] hover:shadow-[0_0_50px_rgba(242,112,7,0.5)] hover:-translate-y-1"
            >
              {data.hero.ctaPrimary.label}
            </a>
            <Link 
              to={data.hero.ctaSecondary.href}
              className="w-full sm:w-auto px-10 py-4 rounded-sm border border-[var(--stroke)] bg-transparent hover:border-[var(--text)] text-[var(--text)] font-rpg font-bold text-lg tracking-wide transition-all hover:bg-[var(--bg1)]"
            >
              {data.hero.ctaSecondary.label}
            </Link>
          </div>
        </div>
      </section>

      {/* 2. VÍDEO */}
      <Section className="!py-0 -mt-20 z-20">
        <div className="max-w-5xl mx-auto">
          <div className="glass-card rounded-xl p-2 md:p-4">
             <div className="relative aspect-video rounded-lg bg-black overflow-hidden group border border-[var(--stroke)]">
                {data.video.embedUrl ? (
                  <iframe 
                    className="w-full h-full"
                    src={data.video.embedUrl}
                    title={data.video.title}
                    frameBorder="0"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                  ></iframe>
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center z-10 bg-[var(--bg0)]">
                     <button className="flex items-center gap-3 px-8 py-4 rounded-full bg-[var(--text)] text-black font-bold shadow-2xl hover:scale-105 transition-transform">
                        <PlayCircle className="w-6 h-6 fill-current" />
                        <span>{data.video.title}</span>
                     </button>
                     <p className="mt-4 text-sm text-white/80 font-medium drop-shadow-md">{data.video.description}</p>
                  </div>
                )}
             </div>
          </div>
        </div>
      </Section>

      {/* 3. COMO JOGAR */}
      <Section darker className="mt-12">
        <div className="mb-12 text-center">
          <h2 className="font-rpg text-3xl font-bold mb-4 text-[var(--text)] uppercase tracking-widest">{data.howToPlay.title}</h2>
          <div className="h-1 w-20 bg-[var(--ember)] mx-auto rounded"></div>
        </div>
        
        <div className="grid md:grid-cols-3 gap-8">
          {data.howToPlay.steps.map((step, index) => (
            <div key={index} className="relative p-8 rounded-xl border border-[var(--stroke)] bg-[var(--card)] hover:border-[var(--muted)] transition-all group overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-[var(--ember)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
              <div className="mb-4 w-12 h-12 rounded-full bg-[var(--bg2)] border border-[var(--stroke)] text-[var(--ember)] font-rpg font-bold text-2xl flex items-center justify-center group-hover:border-[var(--ember)] transition-colors">
                {index + 1}
              </div>
              <p className="text-lg font-medium text-[var(--text)] leading-relaxed">{step}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 4. DIFERENCIAIS */}
      <Section>
        <div className="mb-16 text-center">
          <h2 className="font-rpg text-3xl font-bold mb-4 text-[var(--text)] uppercase tracking-widest">{data.features.title}</h2>
          <div className="h-1 w-20 bg-[var(--flame)] mx-auto rounded"></div>
        </div>

        <div className="grid md:grid-cols-3 gap-12">
          {data.features.items.map((item, idx) => (
            <div key={idx} className="flex flex-col items-center text-center p-6 bg-[var(--bg0)] rounded border border-[var(--stroke)] hover:border-[var(--ember)]/30 transition-all">
              <div className="mb-6 p-4 rounded-full bg-[var(--bg1)] border border-[var(--stroke)]">
                {getFeatureIcon(item.iconId)}
              </div>
              <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-3">{item.title}</h3>
              <p className="text-[var(--muted)] leading-relaxed">{item.description}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 5. MAPA */}
      <Section darker>
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div className="order-2 lg:order-1">
             <div className="relative rounded-lg border border-[var(--stroke)] bg-[var(--bg0)] p-2 shadow-2xl rotate-1 hover:rotate-0 transition-transform duration-500 group">
                <div className="aspect-[4/3] bg-[#1a1a1a] relative overflow-hidden rounded">
                   <div className="absolute inset-0" style={{backgroundImage: 'linear-gradient(#333 1px, transparent 1px), linear-gradient(90deg, #333 1px, transparent 1px)', backgroundSize: '40px 40px', opacity: 0.1}}></div>
                   <div className="absolute top-1/4 left-1/4 w-32 h-32 bg-[var(--stroke)] rounded-full blur-3xl opacity-50"></div>
                   <div className="absolute bottom-1/3 right-1/4 w-48 h-48 bg-[var(--bg2)] rounded-full blur-2xl opacity-60"></div>
                   
                   <div className="absolute inset-0 flex items-center justify-center">
                      <Link 
                        to={data.map.cta.href}
                        className="glass-card px-8 py-4 rounded text-[var(--text)] font-bold uppercase tracking-widest flex items-center gap-2 hover:bg-white/10 transition-all hover:scale-105 border border-[var(--ember)]/30"
                      >
                        <MapIcon className="w-5 h-5 text-[var(--ember)]" />
                        {data.map.cta.label}
                      </Link>
                   </div>
                </div>
                {/* Decoration */}
                <div className="absolute -top-3 -right-3 w-12 h-12 bg-[var(--bg1)] border border-[var(--stroke)] rounded flex items-center justify-center text-[var(--muted)] shadow-xl group-hover:border-[var(--ember)] transition-colors">
                  <Sparkles className="w-6 h-6" />
                </div>
             </div>
          </div>
          
          <div className="order-1 lg:order-2">
            <h2 className="font-rpg text-4xl font-bold mb-6 text-[var(--text)]">
               <span className="bonfire-underline">{data.map.title}</span>
            </h2>
            <p className="text-[var(--muted)] text-lg leading-relaxed mb-8">
              {data.map.text}
            </p>
            <div className="space-y-4">
               {["Regiões Seguras vs. Ermos", "Rotas de Comércio Dinâmicas", "Pontos de Interesse Desbloqueáveis"].map((feature, i) => (
                 <div key={i} className="flex items-center gap-3">
                   <div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full shadow-[0_0_8px_var(--flame)]"></div>
                   <span className="text-[var(--text)] font-medium">{feature}</span>
                 </div>
               ))}
            </div>
          </div>
        </div>
      </Section>

      {/* 6. ATUALIZAÇÕES */}
      <Section>
        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <h2 className="font-rpg text-3xl font-bold mb-8 flex items-center gap-3">
              <ScrollText className="w-6 h-6 text-[var(--muted)]" />
              {data.updates.title}
            </h2>
            <div className="space-y-4">
              {data.updates.items.map((item, idx) => (
                <Link key={idx} to={item.href} className="group block p-6 rounded bg-[var(--bg0)] border border-[var(--stroke)] hover:border-[var(--ember)] transition-all hover:translate-x-1 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <h3 className="text-lg font-bold text-[var(--text)] group-hover:text-[var(--ember)] transition-colors">
                      {item.title}
                    </h3>
                    <span className="text-xs font-mono text-[var(--muted)] px-3 py-1 bg-[var(--bg1)] rounded border border-[var(--stroke)]">
                      {item.date}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="lg:col-span-1">
            <div className="h-full p-8 rounded bg-gradient-to-b from-[var(--bg1)] to-[var(--bg0)] border border-[var(--stroke)] flex flex-col relative overflow-hidden group">
               <div className="absolute top-0 left-0 w-full h-1 bg-[var(--ember)] group-hover:h-2 transition-all"></div>
               <BookOpen className="w-10 h-10 text-[var(--text)] mb-6 group-hover:text-[var(--ember)] transition-colors" />
               <h3 className="font-rpg text-2xl font-bold mb-4">{data.journal.title}</h3>
               <p className="text-[var(--muted)] mb-8 flex-grow">{data.journal.text}</p>
               <Link 
                 to={data.journal.cta.href}
                 className="mt-auto w-full py-3 rounded border border-[var(--stroke)] text-center text-sm font-bold uppercase tracking-widest hover:bg-[var(--text)] hover:text-black transition-colors"
               >
                 {data.journal.cta.label}
               </Link>
            </div>
          </div>
        </div>
      </Section>

      {/* 8. COLABORADOR / CATARSE */}
      <Section darker>
        <div className="rounded-xl relative overflow-hidden border border-[var(--stroke)] bg-[var(--bg1)] shadow-2xl">
           <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(210,23,23,0.1),_transparent_60%)]"></div>
           
           <div className="relative z-10 p-10 md:p-20 text-center">
              <h2 className="font-rpg text-3xl md:text-5xl font-bold mb-6 text-[var(--text)]">
                {data.collaborator.title}
              </h2>
              <p className="text-[var(--muted)] max-w-2xl mx-auto text-lg mb-10 leading-relaxed">
                {data.collaborator.text}
              </p>
              
              <div className="flex flex-col sm:flex-row justify-center gap-6">
                <Link 
                  to={data.collaborator.cta.href}
                  className="px-10 py-4 rounded bg-[var(--text)] text-black font-bold hover:bg-white transition-all hover:scale-105 shadow-xl"
                >
                  {data.collaborator.cta.label}
                </Link>
                <Link 
                  to={data.collaborator.secondary.href}
                  className="px-10 py-4 rounded border border-[var(--stroke)] text-[var(--muted)] hover:text-[var(--text)] hover:border-[var(--text)] transition-all hover:bg-[var(--bg0)]"
                >
                  {data.collaborator.secondary.label}
                </Link>
              </div>
           </div>
        </div>
      </Section>

      {/* 9. QUEM SOMOS */}
      <Section>
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <div>
            <h2 className="font-rpg text-4xl font-bold mb-6 text-[var(--text)]">
              {data.about.title}
            </h2>
            <p className="text-[var(--muted)] text-lg leading-relaxed mb-8">
              {data.about.text}
            </p>
            <Link 
              to={data.about.cta.href}
              className="inline-flex items-center gap-2 text-[var(--ember)] font-bold uppercase tracking-wider hover:text-[var(--flame)] transition-colors text-sm"
            >
              {data.about.cta.label} <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-4">
             <div className="aspect-square bg-[var(--bg0)] rounded border border-[var(--stroke)] flex flex-col items-center justify-center p-6 group hover:border-[var(--ember)] transition-colors">
               <span className="font-rpg text-4xl font-bold text-[var(--text)] mb-2 group-hover:text-[var(--ember)] transition-colors">15+</span>
               <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Narradores</span>
             </div>
             <div className="aspect-square bg-[var(--bg0)] rounded border border-[var(--stroke)] flex flex-col items-center justify-center p-6 group hover:border-[var(--ember)] transition-colors">
               <span className="font-rpg text-4xl font-bold text-[var(--text)] mb-2 group-hover:text-[var(--ember)] transition-colors">500+</span>
               <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Jogadores</span>
             </div>
             <div className="aspect-square bg-[var(--bg0)] rounded border border-[var(--stroke)] flex flex-col items-center justify-center p-6 group hover:border-[var(--ember)] transition-colors">
               <span className="font-rpg text-4xl font-bold text-[var(--text)] mb-2 group-hover:text-[var(--ember)] transition-colors">2k+</span>
               <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Sessões</span>
             </div>
             <div className="aspect-square bg-[var(--bg0)] rounded border border-[var(--stroke)] flex flex-col items-center justify-center p-6 group hover:border-[var(--ember)] transition-colors">
               <span className="font-rpg text-4xl font-bold text-[var(--text)] mb-2 group-hover:text-[var(--ember)] transition-colors">100%</span>
               <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted)]">Autoral</span>
             </div>
          </div>
        </div>
      </Section>

      {/* 10. LIVE / REDES */}
      <Section darker>
        <div className="mb-16">
          <LiveNowCard data={data.liveNow} />
        </div>

        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="font-rpg text-3xl font-bold mb-4 text-[var(--text)]">
            {data.socialSection.title}
          </h2>
          <p className="text-[var(--muted)]">{data.socialSection.text}</p>
        </div>

        <div className="flex flex-wrap justify-center gap-4">
          {data.socialSection.links.map((link, idx) => (
            <a 
              key={idx}
              href={link.href}
              target="_blank" 
              rel="noreferrer"
              className="flex items-center gap-3 px-8 py-4 rounded bg-[var(--bg1)] border border-[var(--stroke)] text-[var(--text)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-all group hover:-translate-y-1 shadow-lg"
            >
              {getSocialIcon(link.iconId)}
              <span className="font-bold text-sm tracking-wide uppercase">{link.label}</span>
            </a>
          ))}
        </div>
      </Section>

    </main>
  );
};

export default Home;
