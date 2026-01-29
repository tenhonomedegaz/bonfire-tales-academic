import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Scroll, 
  User, 
  Dna, 
  Sword, 
  History, 
  CheckSquare, 
  MessageCircle, 
  ArrowRight, 
  AlertTriangle,
  Lightbulb
} from 'lucide-react';

const CriacaoDeFicha: React.FC = () => {
  return (
    <main className="flex-1 bg-[var(--bg0)]">
      {/* Header / Hero */}
      <section className="relative py-20 bg-[var(--bg1)] border-b border-[var(--stroke)] overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(242,112,7,0.1),_transparent_70%)] pointer-events-none" />
        <div className="container mx-auto px-4 text-center relative z-10">
          <div className="inline-flex items-center gap-2 text-[var(--ember)] mb-4">
            <Scroll className="w-6 h-6" />
            <span className="font-bold uppercase tracking-widest text-sm">Grimório do Jogador</span>
          </div>
          <h1 className="font-rpg text-4xl md:text-6xl font-bold text-[var(--text)] mb-6">
            Criação de Ficha
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            Guia rápido para criar seu personagem e começar a jogar pelo Discord.
          </p>
        </div>
      </section>

      <div className="container mx-auto px-4 py-12 max-w-4xl">
        
        {/* Intro Box */}
        <div className="bg-[var(--bg2)] border border-[var(--stroke)] rounded-lg p-6 md:p-8 mb-12 flex flex-col md:flex-row gap-6 items-start shadow-xl">
          <div className="p-3 bg-[var(--bg0)] rounded-full border border-[var(--stroke)] shrink-0">
            <MessageCircle className="w-8 h-8 text-[var(--flame)]" />
          </div>
          <div>
            <h3 className="font-rpg text-xl font-bold text-[var(--text)] mb-2">Primeiro Passo</h3>
            <p className="text-[var(--muted)] mb-4 leading-relaxed">
              Para criar sua ficha, procure um <strong className="text-[var(--text)]">@Recrutador</strong> no Discord. Ele libera a ficha para você e pode te ajudar em qualquer etapa.
            </p>
            <div className="border-l-4 border-[var(--ember)] bg-[var(--bg0)] p-4 rounded-r text-sm text-[var(--muted)] italic">
              <strong className="text-[var(--ember)] not-italic block mb-1 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> Importante
              </strong>
              Este site é guia e referência. A validação final da ficha acontece pelo Discord.
            </div>
          </div>
        </div>

        {/* Steps Container */}
        <div className="space-y-16 relative">
          {/* Vertical Line Connector */}
          <div className="absolute left-4 md:left-8 top-0 bottom-0 w-px bg-gradient-to-b from-[var(--flame)] via-[var(--stroke)] to-transparent hidden md:block opacity-30" />

          {/* Step 1 */}
          <section className="relative md:pl-24">
            <div className="hidden md:flex absolute left-0 top-0 w-16 h-16 rounded-full bg-[var(--bg1)] border border-[var(--stroke)] items-center justify-center font-rpg text-2xl font-bold text-[var(--ember)] z-10 shadow-[0_0_15px_rgba(0,0,0,0.5)]">
              1
            </div>
            
            <div className="flex items-center gap-3 mb-4 md:hidden">
              <span className="w-8 h-8 rounded-full bg-[var(--ember)] text-black font-bold flex items-center justify-center">1</span>
              <h2 className="font-rpg text-2xl font-bold text-[var(--text)]">Imaginação</h2>
            </div>
            <h2 className="hidden md:block font-rpg text-3xl font-bold text-[var(--text)] mb-6">Imaginação</h2>

            <div className="prose prose-invert max-w-none text-[var(--muted)]">
              <p className="text-lg mb-4">
                O primeiro passo é <strong className="text-[var(--text)]">imaginar o seu personagem</strong>: quem ele é, como você quer interpretá-lo e o que aconteceu na vida dele até chegar aqui.
              </p>
              <p className="mb-6">
                Você começa no <strong className="text-[var(--text)]">nível 1</strong>. Isso significa que seu personagem ainda não é uma lenda — ele é “acima da média”, mas está no começo da jornada. Com o tempo, ele pode virar alguém lendário. Pense nisso enquanto cria.
              </p>

              <div className="grid md:grid-cols-2 gap-6 mb-8">
                <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)]">
                  <h4 className="font-bold text-[var(--text)] mb-3 flex items-center gap-2">
                    <User className="w-4 h-4 text-[var(--ember)]" />
                    Defina
                  </h4>
                  <ul className="space-y-2 text-sm list-disc list-inside marker:text-[var(--ember)]">
                    <li>Visual geral, roupas, marcas, postura.</li>
                    <li>Tom de voz, jeito de decidir, limites morais.</li>
                    <li>Objetivo simples (dinheiro, redenção, vingança).</li>
                  </ul>
                </div>
                <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)]">
                  <h4 className="font-bold text-[var(--text)] mb-3 flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-[var(--spark)]" />
                    Exemplos de Conceito
                  </h4>
                  <ul className="space-y-2 text-sm">
                    <li className="flex gap-2"><span className="text-[var(--spark)]">✦</span> Guerreiro Arcano (aço e magia).</li>
                    <li className="flex gap-2"><span className="text-[var(--spark)]">✦</span> Monge Ninja (sombras e furtividade).</li>
                    <li className="flex gap-2"><span className="text-[var(--spark)]">✦</span> Feiticeiro de linhagem dracônica.</li>
                  </ul>
                </div>
              </div>
              <p>
                Use a imaginação para combinar também raças clássicas (Elfos, Anões) e propostas mais fantásticas (incluindo seres incomuns do cenário).
              </p>
            </div>
          </section>

          {/* Step 2 */}
          <section className="relative md:pl-24">
            <div className="hidden md:flex absolute left-0 top-0 w-16 h-16 rounded-full bg-[var(--bg1)] border border-[var(--stroke)] items-center justify-center font-rpg text-2xl font-bold text-[var(--ember)] z-10 shadow-[0_0_15px_rgba(0,0,0,0.5)]">
              2
            </div>

            <div className="flex items-center gap-3 mb-4 md:hidden">
              <span className="w-8 h-8 rounded-full bg-[var(--ember)] text-black font-bold flex items-center justify-center">2</span>
              <h2 className="font-rpg text-2xl font-bold text-[var(--text)]">Raça</h2>
            </div>
            <h2 className="hidden md:block font-rpg text-3xl font-bold text-[var(--text)] mb-6">Raça</h2>

            <div className="prose prose-invert max-w-none text-[var(--muted)]">
              <p className="mb-4">
                Cada personagem pertence a uma <strong>raça</strong> — uma das muitas espécies inteligentes do mundo do Bonfire Tales. Algumas raças possuem <strong>linhagens/sub-raças</strong>.
              </p>
              
              <div className="flex flex-col md:flex-row gap-6 mb-6">
                <div className="flex-1">
                  <p className="mb-2">Sua raça pode conceder traços como:</p>
                  <ul className="list-disc list-inside space-y-1 marker:text-[var(--flame)]">
                    <li>Sentidos especiais.</li>
                    <li>Proficiência com armas ou ferramentas.</li>
                    <li>Proficiência em perícias.</li>
                    <li>Capacidade de usar magias menores.</li>
                  </ul>
                </div>
                <div className="flex-1 bg-[var(--bg2)] p-4 rounded border-l-2 border-[var(--flame)]">
                  <h4 className="font-bold text-[var(--text)] mb-2 flex items-center gap-2">
                    <Dna className="w-4 h-4" /> Tipagens e Essências
                  </h4>
                  <p className="text-sm leading-relaxed">
                    Raças são separadas em tipagens. Um <strong>Essencinata</strong>, por exemplo, tem origem ligada a uma essência (divina, cósmica ou elemental), mas mantém base humanóide.
                    <br/><br/>
                    <em>Ex: Dracônato (humanoide com escamas).</em>
                  </p>
                </div>
              </div>
              <p className="text-sm bg-[var(--bg0)] inline-block px-3 py-1 rounded border border-[var(--stroke)] text-[var(--flame)] font-semibold">
                ⚠ Atenção: registre na ficha todos os traços concedidos pela raça.
              </p>
            </div>
          </section>

          {/* Step 3 */}
          <section className="relative md:pl-24">
            <div className="hidden md:flex absolute left-0 top-0 w-16 h-16 rounded-full bg-[var(--bg1)] border border-[var(--stroke)] items-center justify-center font-rpg text-2xl font-bold text-[var(--ember)] z-10 shadow-[0_0_15px_rgba(0,0,0,0.5)]">
              3
            </div>

            <div className="flex items-center gap-3 mb-4 md:hidden">
              <span className="w-8 h-8 rounded-full bg-[var(--ember)] text-black font-bold flex items-center justify-center">3</span>
              <h2 className="font-rpg text-2xl font-bold text-[var(--text)]">Classe</h2>
            </div>
            <h2 className="hidden md:block font-rpg text-3xl font-bold text-[var(--text)] mb-6">Classe</h2>

            <div className="prose prose-invert max-w-none text-[var(--muted)]">
              <p className="mb-4">
                Todo aventureiro tem uma <strong>classe</strong>. A classe descreve como seu personagem age, seus pontos fortes em combate e como lida com problemas.
              </p>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                <div className="p-4 bg-[var(--bg1)] border border-[var(--stroke)] rounded hover:border-[var(--flame)] transition-colors group">
                  <div className="flex items-center gap-2 font-bold text-[var(--text)] mb-2">
                    <Sword className="w-4 h-4 text-[var(--flame)]" /> Guerreiro
                  </div>
                  <p className="text-sm">Costuma usar armas (espadas, arcos) e tende a ser mais resistente.</p>
                </div>
                <div className="p-4 bg-[var(--bg1)] border border-[var(--stroke)] rounded hover:border-[var(--spark)] transition-colors group">
                  <div className="flex items-center gap-2 font-bold text-[var(--text)] mb-2">
                    <SparklesIcon className="w-4 h-4 text-[var(--spark)]" /> Mago
                  </div>
                  <p className="text-sm">Usa magias e controla o combate, geralmente à distância — em troca de menor resistência.</p>
                </div>
              </div>

              <h4 className="font-bold text-[var(--text)] mb-2">Arquétipos</h4>
              <p>
                Todas as classes possuem <strong>arquétipos</strong> que destacam um estilo específico. Ex: <em>Monge das Sombras</em> vs <em>Monge do Punho do Dragão</em>.
              </p>
            </div>
          </section>

          {/* Step 4 */}
          <section className="relative md:pl-24">
            <div className="hidden md:flex absolute left-0 top-0 w-16 h-16 rounded-full bg-[var(--bg1)] border border-[var(--stroke)] items-center justify-center font-rpg text-2xl font-bold text-[var(--ember)] z-10 shadow-[0_0_15px_rgba(0,0,0,0.5)]">
              4
            </div>

            <div className="flex items-center gap-3 mb-4 md:hidden">
              <span className="w-8 h-8 rounded-full bg-[var(--ember)] text-black font-bold flex items-center justify-center">4</span>
              <h2 className="font-rpg text-2xl font-bold text-[var(--text)]">Antecedente</h2>
            </div>
            <h2 className="hidden md:block font-rpg text-3xl font-bold text-[var(--text)] mb-6">Antecedente e História</h2>

            <div className="prose prose-invert max-w-none text-[var(--muted)]">
              <p className="mb-4">
                Seu personagem precisa de <strong>nome</strong> e <strong>história</strong>. Gaste alguns minutos pensando em aparência, comportamento e vida passada.
              </p>
              <p className="mb-6">
                Depois, escolha um <strong>antecedente</strong>. Ele serve como uma linha-guia para o passado do personagem.
              </p>

              <div className="bg-[#1a0505] border border-red-900/30 p-5 rounded relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-[var(--flame)]" />
                <h4 className="font-bold text-[var(--text)] mb-2 flex items-center gap-2">
                  <History className="w-4 h-4 text-[var(--flame)]" /> Regra de Convivência
                </h4>
                <p className="text-sm text-[var(--muted)]">
                  Seu personagem não pode ter tendência a atrapalhar o grupo de propósito. Sabotar outros jogadores deliberadamente é anti-jogo.
                  <br/><br/>
                  Você pode ser cinzento, egoísta, rabugento ou pragmático. <span className="text-[var(--text)] font-semibold">Só não pode ser alguém que entra para destruir a experiência dos outros.</span>
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Checklist */}
        <section className="mt-20 p-8 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)] shadow-lg">
          <h2 className="font-rpg text-2xl font-bold text-[var(--text)] mb-6 flex items-center gap-3">
            <CheckSquare className="w-6 h-6 text-[var(--spark)]" />
            Checklist Rápido (Pra não travar)
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              "Conceito (quem é e o que quer)",
              "Visual (como se parece)",
              "Raça e traços anotados",
              "Classe e arquétipo planejado",
              "Nome + história curta plausível para nível 1",
              "Antecedente escolhido"
            ].map((item, idx) => (
              <div key={idx} className="flex items-center gap-3 p-3 bg-[var(--bg0)] rounded border border-[var(--stroke)] opacity-80 hover:opacity-100 transition-opacity">
                <div className="w-5 h-5 rounded border border-[var(--muted)] flex items-center justify-center">
                  <div className="w-3 h-3 bg-[var(--muted)] rounded-sm opacity-20"></div>
                </div>
                <span className="text-[var(--text)]">{item}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Finalization / Footer Links */}
        <section className="mt-16 text-center">
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8">Finalização</h2>
          <p className="text-[var(--muted)] mb-8">
            Quando terminar, chame o <strong className="text-[var(--text)]">@Recrutador</strong> no Discord para validar a ficha e liberar seu início no jogo.
          </p>
          
          <div className="flex flex-wrap justify-center gap-4 mb-12">
            <Link to="/jogador/raca" className="px-5 py-2 rounded bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-colors text-sm font-bold uppercase tracking-wide">
              Ver Raças
            </Link>
            <Link to="/jogador/classes" className="px-5 py-2 rounded bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-colors text-sm font-bold uppercase tracking-wide">
              Ver Classes
            </Link>
            <Link to="/jogador/antecedente" className="px-5 py-2 rounded bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-colors text-sm font-bold uppercase tracking-wide">
              Ver Antecedentes
            </Link>
            <Link to="/jogador/talentos" className="px-5 py-2 rounded bg-[var(--bg1)] border border-[var(--stroke)] hover:border-[var(--ember)] hover:text-[var(--ember)] transition-colors text-sm font-bold uppercase tracking-wide">
              Ver Talentos
            </Link>
          </div>

          <a 
            href="https://discord.gg/bonfire-placeholder" 
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-8 py-4 bg-[var(--flame)] text-white font-rpg font-bold text-lg rounded shadow-[0_0_20px_rgba(210,23,23,0.4)] hover:shadow-[0_0_30px_rgba(210,23,23,0.6)] hover:scale-105 transition-all"
          >
            Entrar no Discord <ArrowRight className="w-5 h-5" />
          </a>
        </section>

      </div>
    </main>
  );
};

// Helper icon component for specific use case
const SparklesIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
  >
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
  </svg>
);

export default CriacaoDeFicha;