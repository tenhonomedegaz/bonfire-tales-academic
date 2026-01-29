import React from 'react';
import { 
  Scale, 
  ShieldAlert, 
  AlertTriangle, 
  MicOff, 
  Gavel, 
  Ban, 
  CheckCircle2,
  AlertOctagon
} from 'lucide-react';

const RegrasEPunicoes: React.FC = () => {
  return (
    <main className="flex-1 bg-[var(--bg0)]">
      {/* Hero Section */}
      <section className="relative py-20 bg-[var(--bg1)] border-b border-[var(--stroke)] overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(210,23,23,0.1),_transparent_70%)] pointer-events-none" />
        <div className="container mx-auto px-4 text-center relative z-10">
          <div className="inline-flex items-center gap-2 text-[var(--flame)] mb-4">
            <Scale className="w-6 h-6" />
            <span className="font-bold uppercase tracking-widest text-sm">Código de Conduta</span>
          </div>
          <h1 className="font-rpg text-4xl md:text-6xl font-bold text-[var(--text)] mb-6">
            Regras e Punições
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            Regras básicas do servidor e como funciona o sistema de punições.
          </p>
        </div>
      </section>

      <div className="container mx-auto px-4 py-12 max-w-4xl">
        
        {/* Intro */}
        <div className="prose prose-invert max-w-none text-[var(--muted)] mb-16">
          <p className="text-lg leading-relaxed">
            Para manter um ambiente agradável, seguro e divertido, temos regras simples. Ao participar do servidor, você concorda com estas regras e com o sistema de punições abaixo.
          </p>
          <div className="not-prose bg-[var(--bg2)] border-l-4 border-[var(--spark)] p-4 rounded-r mt-6">
             <p className="text-[var(--text)] font-medium flex items-center gap-2">
               <AlertOctagon className="w-5 h-5 text-[var(--spark)]" />
               Se você tiver dúvida ou precisar denunciar algo, fale com um <span className="text-[var(--spark)] font-bold">Moderador</span>.
             </p>
          </div>
        </div>

        {/* Section: Regras */}
        <section className="mb-20">
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <ShieldAlert className="w-8 h-8 text-[var(--flame)]" />
            Regras do Servidor
          </h2>

          <div className="grid gap-6">
            <RuleItem number={1} title="Respeite para ser respeitado">
              Este é um servidor de comunidade. Trate as pessoas com o respeito que você espera receber.
              Também crie um personagem disposto a jogar em equipe. Não importa tendência, personalidade ou motivação. Seu personagem precisa funcionar com o grupo.
            </RuleItem>

            <RuleItem number={2} title="Conteúdo ofensivo">
              É proibida qualquer manifestação de racismo, LGBTQ+fobia ou qualquer tipo de discriminação.
              Isso vale para avatar do Discord, nome, mensagens, narração, comportamento em campanha e qualquer manifestação direta ou indireta dentro do servidor.
            </RuleItem>

            <RuleItem number={3} title="Assédio">
              Assédio é expressamente proibido. Isso inclui apelidos para envergonhar, ameaças, humilhação e qualquer atitude feita para causar desconforto.
              Em situações graves, a pessoa pode responder civil e criminalmente conforme a legislação brasileira, além de sofrer sanções internas do servidor.
            </RuleItem>

            <RuleItem number={4} title="Política, religião e esportes">
              Evite ferir, provocar ou impor opiniões sobre assuntos polêmicos que possam gerar discórdia. Isso inclui política, religião, esportes e outros temas sensíveis.
            </RuleItem>

            <RuleItem number={5} title="Divulgação">
              Use apenas os canais específicos para divulgar campanhas, streams e artes.
              No geral, não aprovamos venda de produtos ou serviços no servidor sem autorização da equipe.
            </RuleItem>

            <RuleItem number={6} title="Conteúdo e RP +18">
              É estritamente proibido conteúdo sexual, nudez, erotização, fetichização, insinuações explícitas e qualquer interação de teor sexual, mesmo em RP.
            </RuleItem>

            <RuleItem number={7} title="Spam">
              Evite spam, publicações excessivas e caps lock.
            </RuleItem>

            <RuleItem number={8} title="Informações pessoais">
              Não publique informações pessoais, como nome completo, telefone, CPF, RG e dados similares.
            </RuleItem>

            <RuleItem number={9} title="Denúncia">
              Se você quiser denunciar comportamento inapropriado, entre em contato com um <strong className="text-[var(--text)]">Moderador</strong>.
            </RuleItem>

            <RuleItem number={10} title="Punição">
              Quem descumpre regras pode receber alertas. Se o comportamento for recorrente ou grave, punições serão aplicadas.
            </RuleItem>
          </div>
        </section>

        {/* Section: Punições */}
        <section className="mb-20">
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <Gavel className="w-8 h-8 text-[var(--flame)]" />
            Punições do Servidor
          </h2>
          
          <p className="text-[var(--muted)] mb-8 text-lg">
            Para manter a convivência saudável e o ambiente de jogo seguro, usamos um sistema gradual de punições. As punições podem ser:
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
            {["Alertas", "Advertências", "Silêncio", "Banimento"].map((p, i) => (
              <div key={i} className="bg-[var(--bg1)] border border-[var(--stroke)] py-3 px-4 rounded text-center font-bold text-[var(--text)] shadow-sm">
                {p}
              </div>
            ))}
          </div>

          <div className="space-y-12">
            
            {/* Alertas */}
            <div className="bg-[var(--bg1)] p-6 rounded-lg border border-[var(--stroke)]">
              <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-4 flex items-center gap-2">
                <AlertTriangle className="w-6 h-6 text-[var(--spark)]" /> Alertas
              </h3>
              <div className="text-[var(--muted)] space-y-4">
                <p>
                  Alertas são punições leves. Eles são aplicados quando há infração de regra ou conduta nociva que ainda não é grave o suficiente para justificar uma advertência.
                </p>
                <ul className="list-disc list-inside space-y-2 marker:text-[var(--spark)]">
                  <li>Servem como aviso formal de que o comportamento precisa mudar.</li>
                  <li>A moderação analisa contexto e histórico antes de aplicar o alerta.</li>
                  <li>Alertas podem gerar advertências em caso de reincidência.</li>
                </ul>
                <div className="bg-[var(--bg2)] p-4 rounded mt-4">
                  <h4 className="font-bold text-[var(--spark)] text-sm uppercase mb-2">Regras de reincidência</h4>
                  <ul className="text-sm space-y-2">
                    <li>Se o jogador receber um segundo alerta em até 6 meses, pelo mesmo motivo, pode receber uma advertência por reincidência.</li>
                    <li>Se o jogador receber três alertas em até 6 meses, por qualquer motivo, pode receber uma advertência por reincidência.</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Advertências */}
            <div className="bg-[var(--bg1)] p-6 rounded-lg border border-[var(--stroke)]">
              <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-4 flex items-center gap-2">
                <AlertOctagon className="w-6 h-6 text-[var(--ember)]" /> Advertências
              </h3>
              <div className="text-[var(--muted)] space-y-4">
                <p>
                  Advertências são punições mais graves e cumulativas. Representam violações de regra mais sérias ou comportamento nocivo contínuo com a comunidade.
                </p>
                <div className="grid md:grid-cols-3 gap-4 my-4">
                  <div className="bg-[var(--bg0)] border border-[var(--stroke)] p-3 rounded text-center">
                    <span className="block text-[var(--ember)] font-bold text-lg">1ª Advertência</span>
                    <span className="text-xs">1 semana como Infrator</span>
                  </div>
                  <div className="bg-[var(--bg0)] border border-[var(--stroke)] p-3 rounded text-center">
                    <span className="block text-[var(--ember)] font-bold text-lg">2ª Advertência</span>
                    <span className="text-xs">1 mês como Infrator</span>
                  </div>
                  <div className="bg-[var(--bg0)] border border-[var(--flame)] p-3 rounded text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-[var(--flame)] opacity-10"></div>
                    <span className="block text-[var(--flame)] font-bold text-lg">3ª Advertência</span>
                    <span className="text-xs font-bold">Banimento</span>
                  </div>
                </div>
                <div className="text-sm border-l-2 border-[var(--ember)] pl-4">
                  <p className="mb-2"><strong>Relação entre alertas e advertências:</strong></p>
                  <ul className="space-y-1">
                    <li>Se você já tiver 1 advertência, novos alertas podem reiniciar o prazo de prescrição dessa advertência.</li>
                    <li>Dependendo da gravidade e da reincidência, dois alertas adicionais podem gerar uma nova advertência.</li>
                    <li>Se você já tiver 2 advertências, um novo alerta pode resultar na 3ª advertência, levando ao banimento.</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Prescrição */}
            <div className="border border-green-900/30 bg-[#051a0a] p-6 rounded-lg">
               <h3 className="font-rpg text-xl font-bold text-green-400 mb-2 flex items-center gap-2">
                 <CheckCircle2 className="w-5 h-5" /> Prescrição de Advertências
               </h3>
               <p className="text-green-100/70 text-sm leading-relaxed">
                 O servidor entende que pessoas podem mudar. Se você passar <strong className="text-green-300">9 meses</strong> sem receber qualquer punição (alertas, advertências ou silêncio), contando a partir da data da última punição, sua quantidade de advertências diminui em 1. Esse efeito é cumulativo.
               </p>
            </div>

            {/* Silêncio */}
            <div className="bg-[var(--bg1)] p-6 rounded-lg border border-[var(--stroke)]">
              <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-4 flex items-center gap-2">
                <MicOff className="w-6 h-6 text-[var(--muted)]" /> Silêncio
              </h3>
              <p className="text-[var(--muted)] mb-4">
                Silêncio é uma punição temporária usada quando o jogador gera tumulto em canais públicos, aumenta discussões ou atrapalha o andamento das conversas.
              </p>
              <ul className="list-disc list-inside space-y-2 text-[var(--muted)] marker:text-[var(--text)]">
                <li>Durante o silêncio, o jogador não pode enviar mensagens por um período determinado.</li>
                <li>O objetivo é evitar que o conflito cresça e permitir que a pessoa se acalme.</li>
                <li>O silêncio pode ser aplicado junto com alertas ou advertências.</li>
              </ul>
            </div>

            {/* Banimento */}
            <div className="bg-[var(--bg0)] p-6 rounded-lg border border-[var(--flame)] shadow-[0_0_15px_rgba(210,23,23,0.15)]">
              <h3 className="font-rpg text-2xl font-bold text-[var(--flame)] mb-4 flex items-center gap-2">
                <Ban className="w-6 h-6" /> Banimento Imediato
              </h3>
              <p className="text-[var(--muted)] mb-4">
                Banimento imediato é aplicado em condutas extremamente graves, mesmo sem histórico. Exemplos:
              </p>
              <div className="grid md:grid-cols-2 gap-x-8 gap-y-2 text-sm text-[var(--text)]">
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Racismo ou LGBTQ+fobia</div>
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Divulgação de dados (doxxing)</div>
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Ameaças reais ou violência</div>
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Tentativa de golpe ou fraude</div>
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Assédio pesado ou perseguição</div>
                <div className="flex items-center gap-2"><div className="w-1.5 h-1.5 bg-[var(--flame)] rounded-full"></div> Conteúdo sexual ilegal ou extremo</div>
              </div>
              <p className="text-xs text-[var(--muted)] mt-6 italic">
                Em casos assim, além do banimento, o ocorrido pode ser reportado à plataforma e, quando for o caso, às autoridades competentes.
              </p>
            </div>

          </div>
        </section>

        {/* Concordância Footer */}
        <section className="text-center py-8 border-t border-[var(--stroke)]">
          <p className="text-[var(--muted)]">
            Ao participar do servidor, você concorda com estas regras e punições. <br/>
            Nosso objetivo é manter um ambiente saudável, respeitoso e divertido para todos.
          </p>
        </section>

      </div>
    </main>
  );
};

const RuleItem: React.FC<{ number: number; title: string; children: React.ReactNode }> = ({ number, title, children }) => (
  <div className="group bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)] hover:border-[var(--muted)] transition-colors">
    <div className="flex items-start gap-4">
      <div className="flex-shrink-0 w-8 h-8 bg-[var(--bg2)] rounded flex items-center justify-center font-bold text-[var(--ember)] border border-[var(--stroke)] group-hover:border-[var(--ember)] transition-colors">
        {number}
      </div>
      <div>
        <h3 className="font-bold text-[var(--text)] text-lg mb-2">{title}</h3>
        <p className="text-[var(--muted)] text-sm leading-relaxed">
          {children}
        </p>
      </div>
    </div>
  </div>
);

export default RegrasEPunicoes;