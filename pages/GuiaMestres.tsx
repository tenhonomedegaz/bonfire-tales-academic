
import React, { useEffect } from 'react';
import Callout from '../components/mdx/Callout';
import { Steps, Step } from '../components/mdx/Steps';
import Accordion from '../components/mdx/Accordion';
import CopyBlock from '../components/mdx/CopyBlock';
import Badge from '../components/mdx/Badge';
import { 
  Flame, 
  Map, 
  ShieldCheck, 
  Scroll, 
  Gavel, 
  Users, 
  Wrench, 
  Anchor,
  BookOpen
} from 'lucide-react';

const GuiaMestres: React.FC = () => {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <main className="min-h-screen bg-[var(--bg0)] pb-24">
      {/* Hero Header */}
      <section className="relative py-24 bg-gradient-to-b from-[var(--bg1)] to-[var(--bg0)] border-b border-[var(--stroke)] overflow-hidden">
        <div className="absolute inset-0 bg-[noise] opacity-10 pointer-events-none" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] bg-[var(--flame)]/5 rounded-full blur-[120px]" />
        
        <div className="container mx-auto px-4 text-center relative z-10">
          <Badge color="ember">Área da Staff</Badge>
          <h1 className="font-rpg text-5xl md:text-7xl font-bold text-[var(--text)] mt-4 mb-6 tracking-tighter">
            Grimório do <span className="text-gradient">Mestre</span>
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            Tudo o que você precisa para narrar no Bonfire Tales RPG: regras de comunidade, alinhamento de lore e suporte oficial.
          </p>
          
          <div className="flex flex-wrap justify-center gap-4 mt-10">
            <a href="#requisitos" className="px-8 py-3 rounded bg-[var(--flame)] hover:bg-[var(--ember)] text-white font-bold transition-all shadow-lg hover:-translate-y-0.5">
              Quero Mestrar
            </a>
            <a href="https://discord.gg/bonfire" className="px-8 py-3 rounded border border-[var(--stroke)] text-[var(--text)] hover:bg-[var(--bg1)] font-bold transition-all">
              Abrir Missão (Bot)
            </a>
          </div>
        </div>
      </section>

      <div className="container mx-auto px-4 mt-16 flex justify-center">
        {/* Main Content Area - Agora centralizada e sem sidebar */}
        <article className="w-full max-w-4xl">
          
          {/* Section 1 */}
          <section id="boas-vindas" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Flame className="w-8 h-8 text-[var(--flame)]" />
              1) Boas-vindas & Diretrizes Gerais
            </h2>
            <p className="text-[var(--muted)] leading-relaxed mb-6">
              Seja bem-vindo à mesa, Mestre! Esta seção resume o que esperamos de quem narra no Bonfire Tales RPG e o que os jogadores podem esperar de você.
            </p>
            
            <div className="grid md:grid-cols-2 gap-6 my-8">
              <div className="p-6 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)]">
                <h4 className="font-bold text-[var(--text)] mb-3">Nossos Princípios</h4>
                <ul className="space-y-3 text-sm text-[var(--muted)] list-none">
                  <li className="flex gap-2">✦ <span className="text-[var(--text)]">Diversão com segurança:</span> Respeite os limites do grupo.</li>
                  <li className="flex gap-2">✦ <span className="text-[var(--text)]">Escolhas que importam:</span> Evite trilhos narrativos ("railroad").</li>
                  <li className="flex gap-2">✦ <span className="text-[var(--text)]">Coerência:</span> Use o material oficial como âncora.</li>
                </ul>
              </div>
              <div className="p-6 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)]">
                <h4 className="font-bold text-[var(--text)] mb-3">Autonomia</h4>
                <p className="text-sm text-[var(--muted)] leading-relaxed">
                  Você tem total liberdade durante a sessão. Para impactos permanentes no mundo (morte de reis, destruição de cidades), fazemos um alinhamento rápido com os Loremasters.
                </p>
              </div>
            </div>

            <Callout type="warning" title="Quando alinhar previamente?">
              <ul className="list-disc list-inside space-y-1">
                <li>Afeta NPCs centrais (líderes, organizações globais)?</li>
                <li>Muda o mapa físico ou político permanentemente?</li>
                <li>Revela segredos maiores do cenário (deuses, mitologia)?</li>
                <li>Impacta tramas de outros mestres em andamento?</li>
              </ul>
              <p className="mt-3 font-bold">Se respondeu "sim" a qualquer item, fale com um Loremaster.</p>
            </Callout>

            <div className="grid md:grid-cols-3 gap-4 my-8">
              <div className="p-4 rounded border border-emerald-500/20 bg-emerald-500/5 text-center">
                <Badge color="success">Sem Alinhamento</Badge>
                <p className="text-xs text-[var(--muted)] mt-2">Criar taverna, comerciante local ou rumor de vila.</p>
              </div>
              <div className="p-4 rounded border border-amber-500/20 bg-amber-500/5 text-center">
                <Badge color="ember">Recomendado</Badge>
                <p className="text-xs text-[var(--muted)] mt-2">Morte de nobre regional ou fechamento de rota comercial.</p>
              </div>
              <div className="p-4 rounded border border-red-500/20 bg-red-500/5 text-center">
                <Badge color="flame">Necessário</Badge>
                <p className="text-xs text-[var(--muted)] mt-2">Destruir cidade, revelar deuses ou mover fronteiras.</p>
              </div>
            </div>

            <h3 className="font-rpg text-2xl font-bold mt-12 mb-6">Comportamento & Segurança</h3>
            <p className="text-[var(--muted)] mb-6">O mestre age como anfitrião. Combine o tom da aventura antes do início.</p>
            
            <Steps>
              <Step title="Pare a cena">Baixe o tom, fale com calma e suspenda a ação.</Step>
              <Step title="Ouça">Escute as partes envolvidas de forma objetiva.</Step>
              <Step title="Solução Mínima">Corte o tema, mude a cena ou separe os personagens.</Step>
              <Step title="Registre">Anote a decisão no chat da missão para referência futura.</Step>
              <Step title="Escale">Se o problema persistir ou for grave (assédio), chame a staff.</Step>
            </Steps>
          </section>

          {/* Section 2 */}
          <section id="requisitos" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Users className="w-8 h-8 text-[var(--ember)]" />
              2) Requisitos para Mestres
            </h2>
            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 rounded bg-[var(--bg1)] border border-[var(--stroke)]">
                <div className="w-10 h-10 rounded bg-[var(--bg2)] flex items-center justify-center text-[var(--ember)] font-bold">A</div>
                <div>
                  <h4 className="font-bold text-sm text-[var(--text)]">Rank Ametista</h4>
                  <p className="text-xs text-[var(--muted)]">Estar no rank Ametista ou superior como jogador.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 rounded bg-[var(--bg1)] border border-[var(--stroke)]">
                <div className="w-10 h-10 rounded bg-[var(--bg2)] flex items-center justify-center text-[var(--ember)] font-bold">14</div>
                <div>
                  <h4 className="font-bold text-sm text-[var(--text)]">Tempo de Casa</h4>
                  <p className="text-xs text-[var(--muted)]">Ter seu primeiro personagem liberado há pelo menos 14 dias.</p>
                </div>
              </div>
              <div className="flex items-center gap-4 p-4 rounded bg-[var(--bg1)] border border-[var(--stroke)]">
                <div className="w-10 h-10 rounded bg-[var(--bg2)] flex items-center justify-center text-[var(--ember)] font-bold">5e</div>
                <div>
                  <h4 className="font-bold text-sm text-[var(--text)]">Conhecimento de Regras</h4>
                  <p className="text-xs text-[var(--muted)]">Familiaridade com o PHB/DMG (D&D 5e/2024).</p>
                </div>
              </div>
            </div>
            
            <CopyBlock 
              title="Mensagem Sugerida para Candidatura"
              content="Olá! Preenchi o Formulário de Candidatura a Mestre agora há pouco. Fico à disposição para os próximos passos."
            />
          </section>

          {/* Section 3 */}
          <section id="fluxo-de-aprovacao" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <ShieldCheck className="w-8 h-8 text-[var(--ember)]" />
              3) Fluxo de Aprovação (Mestre em Teste)
            </h2>
            <Steps>
              <Step title="Onboarding">Acesso à mesa Premium do Roll20 e contato com um Loremaster.</Step>
              <Step title="Preparação">Envio de um resumo curto da missão para o avaliador.</Step>
              <Step title="Condução">Narrar de 3 a 5 missões com a presença do avaliador em vaga obrigatória.</Step>
              <Step title="Relatórios">Publicar relatórios em até 3 dias após cada mesa.</Step>
              <Step title="Feedback Final">Síntese de pontos fortes e ajustes para efetivação.</Step>
            </Steps>
            <Callout type="info" title="Prazos">
              Primeira missão em até 15 dias após cargo. Missões subsequentes com intervalo máximo de 15 dias.
            </Callout>
          </section>

          {/* Section 4 */}
          <section id="ferramentas" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Wrench className="w-8 h-8 text-[var(--muted)]" />
              4) Ferramentas Recomendadas
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <a href="https://tabletopaudio.com/" className="p-4 rounded border border-[var(--stroke)] hover:border-[var(--ember)] transition-colors">
                <h4 className="font-bold text-sm mb-1">Tabletop Audio</h4>
                <p className="text-xs text-[var(--muted)]">Trilhas e ambiências gratuitas de 10 minutos.</p>
              </a>
              <a href="https://dungeonscrawl.com/" className="p-4 rounded border border-[var(--stroke)] hover:border-[var(--ember)] transition-colors">
                <h4 className="font-bold text-sm mb-1">Dungeon Scrawl</h4>
                <p className="text-xs text-[var(--muted)]">Criador de mapas simples diretamente no navegador.</p>
              </a>
            </div>
          </section>

          {/* Section 5 & 6 */}
          <section id="publicacao" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Scroll className="w-8 h-8 text-[var(--ember)]" />
              5) Publicação & 6) Execução
            </h2>
            <p className="text-[var(--muted)] mb-6">Utilize o comando <code className="text-[var(--ember)]">/missão-criar</code> no bot do Discord.</p>
            
            <Accordion title="Checklist Rápido de Sessão">
              <div className="space-y-4">
                <div>
                  <h5 className="font-bold text-xs uppercase text-[var(--ember)] mb-2">Antes de Começar</h5>
                  <ul className="text-sm text-[var(--muted)] list-disc list-inside">
                    <li>Confirmar mínimo de 3 jogadores.</li>
                    <li>Aplicar Baixa Prioridade (/baixa-adicionar).</li>
                    <li>Postar bloco de "Gastos e Ganhos".</li>
                  </ul>
                </div>
                <div>
                  <h5 className="font-bold text-xs uppercase text-[var(--ember)] mb-2">Pós-Sessão</h5>
                  <ul className="text-sm text-[var(--muted)] list-disc list-inside">
                    <li>Atualizar relatório completo em até 3 dias.</li>
                    <li>Registrar impactos permanentes no mundo.</li>
                    <li>Validar moedas de mestragem (100 MM a cada 02:30h).</li>
                  </ul>
                </div>
              </div>
            </Accordion>

            <CopyBlock 
              title="Modelo de Relatório Completo"
              content={`Missão: Título da Missão\nMestre: Nome\nData: DD/MM/AAAA\nRank: @Rank\nParticipantes: Nomes\nGanhos e Gastos: Itens, ouro, consumos\nResumo: Breve explicação...\nAcontecimentos Importantes: Impactos em personagens e cenário.`}
            />
          </section>

          {/* Section 7 */}
          <section id="divisao" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <BookOpen className="w-8 h-8 text-[var(--ember)]" />
              7) Divisão de Sessões
            </h2>
            <Callout type="info">
              Intervalo máximo de 15 dias entre partes. Conclusão total em até 30 dias.
            </Callout>
            <CopyBlock 
              title="Fechamento de Parte"
              content="Parte X finalizada em DD/MM — duração: __h — total: __h. Próxima parte prevista para janela DD/MM-DD/MM. Atualizem Gastos e Ganhos."
            />
          </section>

          {/* Section 8 */}
          <section id="hierarquia" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Anchor className="w-8 h-8 text-[var(--ember)]" />
              8) Hierarquia de Mestres
            </h2>
            <div className="grid gap-4">
              <div className="p-5 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)] group hover:border-[var(--ember)] transition-all">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-[var(--text)]">Mestre</h4>
                  <Badge color="success">Ativo</Badge>
                </div>
                <p className="text-xs text-[var(--muted)]">Narra todos os ranks e missões de Background.</p>
              </div>
              <div className="p-5 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)] group hover:border-[var(--ember)] transition-all">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-[var(--text)]">Mestre Conselheiro</h4>
                  <Badge color="ember">15+ Mesas</Badge>
                </div>
                <p className="text-xs text-[var(--muted)]">Itens mágicos, maldições e publicações no jornal mundial.</p>
              </div>
              <div className="p-5 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)] group hover:border-[var(--ember)] transition-all">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-[var(--text)]">Mestre Ancião</h4>
                  <Badge color="ember">Especialista</Badge>
                </div>
                <p className="text-xs text-[var(--muted)]">Missões de Ascensão e planejamento de eventos oficiais.</p>
              </div>
              <div className="p-5 rounded-lg bg-[var(--bg1)] border border-[var(--stroke)] group hover:border-[var(--ember)] transition-all">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-[var(--text)]">Grão-Mestre Ancião</h4>
                  <Badge color="flame">Lendário</Badge>
                </div>
                <p className="text-xs text-[var(--muted)]">Missões de Lenda e mudanças geopolíticas massivas.</p>
              </div>
            </div>
          </section>

          {/* Section 9 */}
          <section id="penalidades" className="scroll-mt-28 mb-20">
            <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3">
              <Gavel className="w-8 h-8 text-[var(--flame)]" />
              9) Penalidades & Procedimentos
            </h2>
            
            <Accordion title="Banimento em Mesas (Pelo Mestre)">
              <p className="text-sm text-[var(--muted)] mb-4">Restrição aplicada pelo mestre que vale somente para suas mesas.</p>
              <h5 className="font-bold text-xs uppercase text-[var(--flame)] mb-2">Motivos Elegíveis</h5>
              <ul className="text-sm text-[var(--muted)] mb-4 list-disc list-inside">
                <li>Assédio ou hostilidade após orientação.</li>
                <li>Sabotagem proposital de cena.</li>
                <li>Quebra grave de regras (trapaça, flood).</li>
              </ul>
              <CopyBlock 
                title="Modelo de Registro de Banimento"
                content={`Banimento de Mesa — Registro\nMestre: ____\nJogador/Personagem: ____\nMotivo: ____\nEvidências: (link ou print)\nDuração: 7/14/30 dias.`}
              />
            </Accordion>

            <Accordion title="Escala de Penalidades (Mestres)">
              <div className="space-y-4">
                <div className="border-l-2 border-amber-500 pl-4">
                  <h6 className="font-bold text-sm">1ª Ocorrência Leve</h6>
                  <p className="text-xs text-[var(--muted)]">Atrasos sistemáticos ou relatórios fora do prazo: BP + Perda de Aventuras.</p>
                </div>
                <div className="border-l-2 border-red-500 pl-4">
                  <h6 className="font-bold text-sm">Falta Grave</h6>
                  <p className="text-xs text-[var(--muted)]">Abuso de poder, assédio ou fraude: Revogação do cargo e perda da mesa Premium.</p>
                </div>
              </div>
            </Accordion>

            <Callout type="danger" title="Quando chamar a Staff?">
              Assédio, discriminação, disputa insolúvel entre jogadores ou descumprimento sistemático de regras.
            </Callout>
          </section>

        </article>
      </div>
    </main>
  );
};

export default GuiaMestres;
