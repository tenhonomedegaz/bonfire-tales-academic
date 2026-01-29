import React from 'react';
import { Target, Trophy, Coins, Users, Clock, AlertTriangle, Shield, Sword } from 'lucide-react';

const Missoes: React.FC = () => {
  return (
    <main className="flex-1 bg-[var(--bg0)]">
      {/* Hero Section */}
      <section className="relative py-20 bg-[var(--bg1)] border-b border-[var(--stroke)] overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(242,112,7,0.1),_transparent_70%)] pointer-events-none" />
        <div className="container mx-auto px-4 text-center relative z-10">
          <div className="inline-flex items-center gap-2 text-[var(--ember)] mb-4">
            <Target className="w-6 h-6" />
            <span className="font-bold uppercase tracking-widest text-sm">Sistema de Missões</span>
          </div>
          <h1 className="font-rpg text-4xl md:text-6xl font-bold text-[var(--text)] mb-6">
            Missões e Ranks
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            Como funcionam missões, aventuras, ranks, recompensas, vagas e penalidades no servidor.
          </p>
        </div>
      </section>

      <div className="container mx-auto px-4 py-12 max-w-4xl">
        
        {/* Intro */}
        <div className="prose prose-invert max-w-none text-[var(--muted)] mb-12">
          <p className="text-lg leading-relaxed">
            Esta seção explica como funciona o sistema de missões e recompensas do servidor. Muitos pontos lembram uma campanha tradicional, mas aqui existem regras próprias para organizar fila, recompensas e participação.
          </p>
        </div>

        {/* 1. Níveis, Aventuras e Ranks */}
        <section className="mb-16">
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <Trophy className="w-8 h-8 text-[var(--spark)]" />
            Níveis, Aventuras, Ranks e Conquistas
          </h2>
          <p className="text-[var(--muted)] mb-8">
            Conforme seu personagem completa missões, ele recebe <strong className="text-[var(--text)]">Aventuras</strong>. Ao acumular Aventuras suficientes, ele avança de nível e pode desbloquear <strong className="text-[var(--text)]">Conquistas</strong> do servidor.
          </p>

          <div className="overflow-x-auto rounded border border-[var(--stroke)] bg-[var(--bg1)] shadow-lg">
            <table className="w-full text-left text-sm whitespace-nowrap md:whitespace-normal">
              <thead className="bg-[var(--bg2)] text-[var(--ember)] uppercase font-bold tracking-wider">
                <tr>
                  <th className="px-6 py-4 border-b border-[var(--stroke)]">Nível / Marco</th>
                  <th className="px-6 py-4 border-b border-[var(--stroke)] text-right">Aventuras</th>
                  <th className="px-6 py-4 border-b border-[var(--stroke)]">Rank</th>
                  <th className="px-6 py-4 border-b border-[var(--stroke)]">Conquista</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--stroke)] text-[var(--muted)]">
                {/* Obsidiana */}
                {[
                  { lvl: 1, adv: 0, rank: "Obsidiana", ach: "" },
                  { lvl: 2, adv: 1, rank: "Obsidiana", ach: "" },
                  { lvl: 3, adv: 3, rank: "Obsidiana", ach: "" },
                  { lvl: 4, adv: 6, rank: "Obsidiana", ach: "" },
                ].map((row, i) => (
                   <tr key={i} className="hover:bg-[var(--bg0)] transition-colors bg-[var(--bg1)]">
                     <td className="px-6 py-3 font-medium text-[var(--text)]">{row.lvl}</td>
                     <td className="px-6 py-3 text-right font-mono">{row.adv}</td>
                     <td className="px-6 py-3 text-gray-500">{row.rank}</td>
                     <td className="px-6 py-3">{row.ach}</td>
                   </tr>
                ))}
                
                {/* Ametista */}
                {[
                  { lvl: 5, adv: 9, rank: "Ametista", ach: "Missão Especial", color: "text-purple-400" },
                  { lvl: 6, adv: 13, rank: "Ametista", ach: "", color: "text-purple-400" },
                  { lvl: 7, adv: 17, rank: "Ametista", ach: "", color: "text-purple-400" },
                  { lvl: 8, adv: 22, rank: "Ametista", ach: "", color: "text-purple-400" },
                ].map((row, i) => (
                   <tr key={`am-${i}`} className="hover:bg-[var(--bg0)] transition-colors bg-purple-900/5">
                     <td className="px-6 py-3 font-medium text-[var(--text)]">{row.lvl}</td>
                     <td className="px-6 py-3 text-right font-mono">{row.adv}</td>
                     <td className={`px-6 py-3 font-bold ${row.color}`}>{row.rank}</td>
                     <td className="px-6 py-3">{row.ach && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-purple-900/30 text-purple-200 border border-purple-800">{row.ach}</span>}</td>
                   </tr>
                ))}

                {/* Topázio */}
                {[
                  { lvl: 9, adv: 28, rank: "Topázio", ach: "Missão de Item Raro", color: "text-yellow-400" },
                  { lvl: 10, adv: 35, rank: "Topázio", ach: "", color: "text-yellow-400" },
                  { lvl: 11, adv: 42, rank: "Topázio", ach: "", color: "text-yellow-400" },
                  { lvl: 12, adv: 50, rank: "Topázio", ach: "", color: "text-yellow-400" },
                ].map((row, i) => (
                   <tr key={`tp-${i}`} className="hover:bg-[var(--bg0)] transition-colors bg-yellow-900/5">
                     <td className="px-6 py-3 font-medium text-[var(--text)]">{row.lvl}</td>
                     <td className="px-6 py-3 text-right font-mono">{row.adv}</td>
                     <td className={`px-6 py-3 font-bold ${row.color}`}>{row.rank}</td>
                     <td className="px-6 py-3">{row.ach && <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold bg-yellow-900/30 text-yellow-200 border border-yellow-800">{row.ach}</span>}</td>
                   </tr>
                ))}

                {/* Esmeralda */}
                {[
                  { lvl: 13, adv: 59, rank: "Esmeralda", ach: "Espaço de Personagem* + Item Muito Raro", color: "text-emerald-400" },
                  { lvl: 14, adv: 69, rank: "Esmeralda", ach: "", color: "text-emerald-400" },
                  { lvl: 15, adv: 79, rank: "Esmeralda", ach: "", color: "text-emerald-400" },
                  { lvl: 16, adv: 90, rank: "Esmeralda", ach: "", color: "text-emerald-400" },
                ].map((row, i) => (
                   <tr key={`em-${i}`} className="hover:bg-[var(--bg0)] transition-colors bg-emerald-900/5">
                     <td className="px-6 py-3 font-medium text-[var(--text)]">{row.lvl}</td>
                     <td className="px-6 py-3 text-right font-mono">{row.adv}</td>
                     <td className={`px-6 py-3 font-bold ${row.color}`}>{row.rank}</td>
                     <td className="px-6 py-3 text-xs">{row.ach}</td>
                   </tr>
                ))}

                {/* Âmbar */}
                {[
                  { lvl: 17, adv: 102, rank: "Âmbar", ach: "Missão de Item Lendário", color: "text-orange-400" },
                  { lvl: 18, adv: 114, rank: "Âmbar", ach: "", color: "text-orange-400" },
                  { lvl: 19, adv: 127, rank: "Âmbar", ach: "", color: "text-orange-400" },
                ].map((row, i) => (
                   <tr key={`am2-${i}`} className="hover:bg-[var(--bg0)] transition-colors bg-orange-900/5">
                     <td className="px-6 py-3 font-medium text-[var(--text)]">{row.lvl}</td>
                     <td className="px-6 py-3 text-right font-mono">{row.adv}</td>
                     <td className={`px-6 py-3 font-bold ${row.color}`}>{row.rank}</td>
                     <td className="px-6 py-3 text-xs">{row.ach}</td>
                   </tr>
                ))}
                
                {/* High Ranks */}
                <tr className="hover:bg-[var(--bg0)] transition-colors bg-red-900/10">
                   <td className="px-6 py-3 font-medium text-[var(--text)]">20</td>
                   <td className="px-6 py-3 text-right font-mono">140</td>
                   <td className="px-6 py-3 font-bold text-red-500">Rubi</td>
                   <td className="px-6 py-3 text-xs">Espaço de Personagem*</td>
                </tr>
                <tr className="hover:bg-[var(--bg0)] transition-colors bg-cyan-900/10">
                   <td className="px-6 py-3 font-medium text-[var(--text)]">Epic Boon</td>
                   <td className="px-6 py-3 text-right font-mono">160</td>
                   <td className="px-6 py-3 font-bold text-cyan-300">Diamante</td>
                   <td className="px-6 py-3 text-xs">Item Muito Raro² + Feat Epic Boon</td>
                </tr>
                 <tr className="hover:bg-[var(--bg0)] transition-colors bg-cyan-900/10">
                   <td className="px-6 py-3 font-medium text-[var(--text)]">Ascensão</td>
                   <td className="px-6 py-3 text-right font-mono">180</td>
                   <td className="px-6 py-3 font-bold text-cyan-300">Diamante</td>
                   <td className="px-6 py-3 text-xs">Escrita da Ascensão</td>
                </tr>
                <tr className="hover:bg-[var(--bg0)] transition-colors bg-amber-200/5">
                   <td className="px-6 py-3 font-medium text-[var(--spark)]">Lenda</td>
                   <td className="px-6 py-3 text-right font-mono text-[var(--spark)]">200</td>
                   <td className="px-6 py-3 font-bold text-[var(--spark)]">Lenda</td>
                   <td className="px-6 py-3 text-xs text-[var(--text)]">Missão de Lenda + Título + Melhoria</td>
                </tr>

              </tbody>
            </table>
          </div>
          
          <div className="mt-6 text-sm text-[var(--muted)] space-y-2 bg-[var(--bg2)] p-4 rounded border-l-4 border-[var(--stroke)]">
             <p><strong className="text-[var(--text)]">* Espaço de Personagem:</strong> você ganha permanentemente 1 slot adicional de personagem quando conquistar isso pela primeira vez. Não se repete ao alcançar o marco com outro personagem.</p>
             <p><strong className="text-[var(--text)]">² Missão de Item Muito Raro:</strong> pode ser aplicada novamente conforme critérios do servidor e da moderação (detalhes podem variar por temporada).</p>
          </div>
        </section>

        {/* 2. Recompensas */}
        <section className="mb-16">
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <Coins className="w-8 h-8 text-[var(--spark)]" />
            Recompensas em Missões
          </h2>

          <div className="grid md:grid-cols-2 gap-8 mb-8">
             <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
                <h3 className="font-bold text-[var(--text)] mb-4 flex items-center gap-2">Regras Gerais</h3>
                <ul className="space-y-3 text-sm text-[var(--muted)]">
                   <li className="flex gap-2 items-start"><span className="text-[var(--ember)] mt-1">✦</span> O ouro recebido é proporcional ao <strong>Rank</strong> do personagem.</li>
                   <li className="flex gap-2 items-start"><span className="text-[var(--ember)] mt-1">✦</span> Se uma mesa não for concluída e virar continuação, o valor acumula e é entregue ao fim da última parte.</li>
                   <li className="flex gap-2 items-start"><span className="text-[var(--ember)] mt-1">✦</span> O Mestre não é obrigado a conceder recompensa se não fizer sentido narrativamente (ex: missão pessoal ou favor).</li>
                   <li className="flex gap-2 items-start"><span className="text-[var(--ember)] mt-1">✦</span> O loot pode ser narrado como materiais, ferramentas, armas ou itens coletados.</li>
                </ul>
             </div>

             <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
                <h3 className="font-bold text-[var(--text)] mb-4 flex items-center gap-2">Ouro por Rank</h3>
                <div className="space-y-2 text-sm">
                   {[
                     { r: "Obsidiana", g: "120 PO" },
                     { r: "Ametista", g: "250 PO" },
                     { r: "Topázio", g: "400 PO" },
                     { r: "Esmeralda", g: "650 PO" },
                     { r: "Âmbar", g: "800 PO" },
                     { r: "Rubi", g: "1000 PO" },
                     { r: "Diamante", g: "1200 PO" },
                   ].map((item, i) => (
                     <div key={i} className="flex justify-between border-b border-[var(--stroke)] last:border-0 pb-1 last:pb-0">
                       <span className="text-[var(--muted)]">{item.r}</span>
                       <span className="font-mono text-[var(--spark)]">{item.g}</span>
                     </div>
                   ))}
                </div>
             </div>
          </div>

          <h3 className="font-bold text-[var(--text)] mb-4 flex items-center gap-2">
             <Clock className="w-5 h-5 text-[var(--muted)]" /> Aventuras e Recompensas por tempo
          </h3>
          <div className="overflow-x-auto rounded border border-[var(--stroke)]">
             <table className="w-full text-left text-sm">
               <thead className="bg-[var(--bg2)] text-[var(--muted)] uppercase font-bold text-xs">
                 <tr>
                   <th className="px-4 py-3">Tempo de Aventura</th>
                   <th className="px-4 py-3">Ganho</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-[var(--stroke)] text-[var(--muted)] bg-[var(--bg1)]">
                 <tr><td className="px-4 py-3">2h30min até 4h59min</td><td className="px-4 py-3 text-[var(--text)]">1 Aventura e 1 Recompensa</td></tr>
                 <tr><td className="px-4 py-3">5h até 9h59min</td><td className="px-4 py-3 text-[var(--text)]">2 Aventuras e 2 Recompensas</td></tr>
                 <tr><td className="px-4 py-3">10h até 14h59min</td><td className="px-4 py-3 text-[var(--text)]">3 Aventuras e 3 Recompensas</td></tr>
                 <tr><td className="px-4 py-3">15h até 19h59min</td><td className="px-4 py-3 text-[var(--text)]">4 Aventuras e 4 Recompensas</td></tr>
                 <tr><td className="px-4 py-3">A cada 5h após 20h</td><td className="px-4 py-3 text-[var(--text)]">+1 Aventura e +1 Recompensa</td></tr>
               </tbody>
             </table>
          </div>
        </section>

        {/* 3. Vagas e Inscrição */}
        <section className="mb-16">
           <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <Users className="w-8 h-8 text-[var(--flame)]" />
            Vagas e Inscrição
          </h2>

          <div className="mb-8">
             <h3 className="font-bold text-[var(--text)] mb-4">Tipos de Vagas</h3>
             <div className="space-y-4">
                {[
                  { t: "Vagas Obrigatórias", d: "Dedicadas a quem é essencial para a missão (quem busca, pesquisa rumores). Máx 25%." },
                  { t: "Vagas Prioritárias", d: "Quem já participou ou tem info importante. Máx 25%." },
                  { t: "Vagas de Colaboradores", d: "Missões Ametista+ devem reservar 25%. Se ninguém pegar, libera." },
                  { t: "Vagas Normais", d: "Ordem de chegada. Mínimo 50% das vagas." },
                  { t: "Prioridade Baixa (PB)", d: "Quem jogou nas últimas 48h entra por último na fila normal." },
                  { t: "Infratores", d: "Jogadores sob penalidade entram sempre por último." },
                ].map((v, i) => (
                  <div key={i} className="flex gap-3 text-sm">
                    <div className="min-w-[4px] bg-[var(--stroke)] rounded-full"></div>
                    <div>
                      <strong className="text-[var(--text)] block mb-1">{v.t}</strong>
                      <span className="text-[var(--muted)]">{v.d}</span>
                    </div>
                  </div>
                ))}
             </div>
          </div>

          <div className="bg-[var(--bg2)] border border-[var(--stroke)] p-6 rounded-lg mb-10">
             <h3 className="font-bold text-[var(--ember)] mb-4 text-sm uppercase tracking-widest">Ordem de Preenchimento</h3>
             <div className="flex flex-wrap items-center gap-y-2 text-sm text-[var(--muted)] font-medium">
                <span className="text-[var(--text)]">Obrigatória</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--text)]">Prioritária</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--text)]">Colaborador</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--spark)] font-bold bg-[var(--spark)]/10 px-2 py-0.5 rounded">Normal</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--text)]">Colaborador (PB)</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--text)]">Prioridade Baixa</span> 
                <span className="mx-2 text-[var(--ember)] text-lg leading-none">→</span>
                
                <span className="text-[var(--flame)] font-bold">Infratores</span>
             </div>
          </div>

          <div className="space-y-8">
             <div>
                <h3 className="font-rpg text-2xl font-bold text-[var(--text)] mb-4">Regras de Inscrições</h3>
                <ul className="list-disc list-inside space-y-2 text-[var(--muted)] marker:text-[var(--flame)]">
                   <li>Ao postar o link do personagem na inscrição, o jogador confirma que vai participar da mesa.</li>
                   <li>O jogador pode cancelar a inscrição até 1h antes do começo da sessão sem penalidade.</li>
                   <li>O limite de atraso é de 15 minutos. Depois disso, punições podem ser aplicadas.</li>
                </ul>
             </div>

             <div className="grid md:grid-cols-2 gap-8">
                <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
                   <h4 className="font-bold text-[var(--text)] mb-3">Confirmação e transparência</h4>
                   <ul className="space-y-2 text-sm text-[var(--muted)]">
                      <li><span className="text-[var(--ember)]">✦</span> Se o horário de confirmação for diferente, deve estar explícito no post.</li>
                      <li><span className="text-[var(--ember)]">✦</span> Mudanças no horário devem marcar o rank envolvido.</li>
                      <li><span className="text-[var(--ember)]">✦</span> Mestre deve usar a lista de emotes no #sala-de-mestres para indicar vagas.</li>
                      <li><span className="text-[var(--ember)]">✦</span> <strong>Recomendação:</strong> Atualizar lista 2x/dia e 1h30min antes.</li>
                   </ul>
                </div>
                <div className="bg-[var(--bg1)] p-6 rounded border border-[var(--stroke)]">
                   <h4 className="font-bold text-[var(--text)] mb-3">Mudanças de data e horário</h4>
                   <p className="text-sm text-[var(--muted)] mb-4">
                      Qualquer alteração deve ser feita com <strong>4 horas de antecedência</strong> e deve marcar os ranks participantes.
                   </p>
                   <p className="text-sm text-[var(--muted)]">
                      Imprevistos são analisados caso a caso. Mestres representam a confiabilidade do servidor.
                   </p>
                </div>
             </div>

             <div className="grid md:grid-cols-2 gap-8">
                <div>
                   <h4 className="font-bold text-[var(--text)] mb-2">Inscrição por Rank</h4>
                   <p className="text-sm text-[var(--muted)] mb-4">
                      Jogadores só podem se inscrever se tiverem o rank permitido. Inscrições indevidas devem ser negadas pelo Mestre.
                   </p>
                   
                   <h4 className="font-bold text-[var(--text)] mb-2">Abertura para outros ranks</h4>
                   <p className="text-sm text-[var(--muted)]">
                      Se sobrar vaga, o Mestre pode marcar o próximo rank. Apenas inscrições <strong>após</strong> essa marcação valem.
                   </p>
                </div>
                
                <div>
                   <div className="bg-[var(--bg1)] p-4 rounded border border-[var(--stroke)]">
                      <h4 className="font-bold text-[var(--text)] mb-2 flex items-center gap-2">
                         <Sword className="w-4 h-4 text-[var(--spark)]" /> Ajuste temporário de nível
                      </h4>
                      <p className="text-sm text-[var(--muted)] mb-2">
                         Se entrar em missão de nível maior, o personagem sobe temporariamente para equilibrar.
                      </p>
                      <ul className="list-disc list-inside text-sm text-[var(--muted)] marker:text-[var(--spark)]">
                         <li>Recebe 1 item por nível subido.</li>
                         <li>Itens somem ao fim da missão.</li>
                      </ul>
                      <p className="text-xs text-[var(--muted)] mt-2 italic">Ex: Nível 1 em missão Nível 3 ganha 1 item lvl 1 e 1 item lvl 2.</p>
                   </div>
                </div>
             </div>
          </div>
        </section>

        {/* 4. Penalidades */}
        <section>
          <h2 className="font-rpg text-3xl font-bold text-[var(--text)] mb-8 flex items-center gap-3 pb-4 border-b border-[var(--stroke)]">
            <AlertTriangle className="w-8 h-8 text-[var(--flame)]" />
            Penalidades
          </h2>
          
          <p className="text-[var(--muted)] mb-8">
             Penalidades existem para proteger o tempo do grupo e a organização do servidor. Elas podem ser mais severas em casos repetidos, a critério de Moderadores e Administradores.
          </p>

          <div className="grid md:grid-cols-3 gap-6">
             <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)] hover:border-[var(--flame)] transition-colors group">
                <div className="flex items-center gap-2 font-bold text-[var(--text)] mb-3">
                   <Shield className="w-5 h-5 text-[var(--muted)]" /> Penalidade para Jogadores
                </div>
                <p className="text-sm text-[var(--muted)] mb-2">
                   Confirmou e não foi? Pode receber:
                </p>
                <ul className="list-disc list-inside text-sm text-[var(--muted)] mb-4 marker:text-[var(--flame)]">
                   <li>Prioridade Baixa (PB).</li>
                   <li>-1 Aventura e -1 Recompensa (na próxima).</li>
                </ul>
                 <p className="text-xs text-[var(--muted)] border-t border-[var(--stroke)] pt-2">
                    1ª vez: apenas PB.<br/>
                    2ª vez: PB + Redução.
                </p>
             </div>

             <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)] hover:border-[var(--flame)] transition-colors group">
                <div className="flex items-center gap-2 font-bold text-[var(--text)] mb-3">
                   <Users className="w-5 h-5 text-[var(--muted)]" /> Penalidade para Mestres
                </div>
                 <p className="text-sm text-[var(--muted)] mb-2">
                    Faltou sem justificativa?
                </p>
                <ul className="list-disc list-inside text-sm text-[var(--muted)] marker:text-[var(--flame)]">
                   <li>Prioridade Baixa (PB).</li>
                   <li>-1 Adv/Rec na próxima que jogar.</li>
                   <li>-1 Adv/Rec na próxima que narrar.</li>
                </ul>
             </div>

             <div className="bg-[var(--bg1)] p-5 rounded border border-[var(--stroke)] hover:border-[var(--flame)] transition-colors group">
                <div className="flex items-center gap-2 font-bold text-[var(--text)] mb-3">
                   <Clock className="w-5 h-5 text-[var(--muted)]" /> Logs e Prazo
                </div>
                <p className="text-sm text-[var(--muted)] mb-3">
                   Prazo de 7 dias para atualizar log.
                </p>
                <ul className="list-disc list-inside text-sm text-[var(--muted)] marker:text-[var(--flame)]">
                   <li>Sem atualização = log recusado.</li>
                   <li>Fora do prazo pode ser negado (perda de itens/XP).</li>
                </ul>
             </div>
          </div>
        </section>

      </div>
    </main>
  );
};

export default Missoes;