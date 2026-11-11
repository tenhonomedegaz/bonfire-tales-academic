import ptBR, { format, differenceInSeconds, secondsInMinute } from 'date-fns';
import { EmbedBuilder, Guild } from 'discord.js';
import { container } from 'tsyringe';

import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { thumbnails, bonfireRpgRankRoles, rankWithEmoji } from '@/config/bonfire';
import { ShowCurrentDedicatedRankUseCase } from '@/modules/rpg/dedicatedRank/useCases/ShowCurrentDedicatedRankUseCase';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { formatInBrazil } from '@/shared/util/dateTime';
import { questRewardAmount } from '@/modules/rpg/quests/services/questReward';

// Mapeamento de rank para braseiros (moedas de evento)
const RANK_TO_BRASEIROS: Record<string, number> = {
  'Obsidiana (1-4)': 2,
  'Ametista (5-8)': 3,
  'Topázio (9-12)': 4,
  'Esmeralda (13-16)': 5,
  'Âmbar (17-19)': 6,
  'Rubi (20)': 6,
};

/* ----------------------------------------------------------- */
/* UTILITIES                                                   */
/* ----------------------------------------------------------- */

function decodeQuestStatus(status: string) {
  switch (status) {
    case 'idle': return '🆕 Não iniciada';
    case 'running': return '▶️ Em andamento';
    case 'paused': return '⏸️ Pausada';
    case 'frozen': return '⏹️ Congelada';
    case 'finished': return '⏏️ Finalizada';
    default: return '-';
  }
}

function decodeTimeEvent(eventType: string) {
  switch (eventType) {
    case 'run': return '▶️ Iniciou';
    case 'pause': return '⏸️ Pausou';
    case 'freeze': return '⏹️ Congelou';
    case 'finish': return '⏏️ Finalizou Missão';
    default: return '-';
  }
}

function decodePlayerType(playerType: string) {
  switch (playerType) {
    case 'high-priority': return '🏅 Prioritário';
    case 'subscriber': return '👑 Colab';
    case 'fill': return '🔹 Completar';
    case 'normal': return '👤 Normal';
    default: return '-';
  }
}

function formatMinutes(totalMinutes = 0): string {
  return `${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m`;
}

function buildPartialRewardLines(quest: Quest): string[] {
  return (quest.questPlayers ?? [])
    .filter((player) => player.removedWithReward)
    .map((player) => (
      `<@${player.userId}> - ${player.rewardAmount ?? 0} recompensa(s) por ${formatMinutes(player.rewardMinutes ?? 0)}`
    ));
}

function buildRewardPlayersList(quest: Quest): string {
  const playersByUserId = new Map<string, {
    userId: string;
    type: string;
    removedWithReward?: boolean;
    rewardMinutes?: number;
    rewardAmount?: number;
  }>();

  quest.questPlayers?.forEach((player) => {
    if (player.userId) {
      playersByUserId.set(player.userId, {
        userId: player.userId,
        type: player.type,
        removedWithReward: player.removedWithReward,
        rewardMinutes: player.rewardMinutes,
        rewardAmount: player.rewardAmount,
      });
    }
  });

  quest.highPriorityPlayers?.forEach((userId) => {
    if (userId && !playersByUserId.has(userId)) {
      playersByUserId.set(userId, {
        userId,
        type: 'high-priority',
      });
    }
  });

  quest.subscribedPlayers?.forEach((player: any) => {
    const userId = typeof player === 'string' ? player : player.userId;
    if (userId && !playersByUserId.has(userId)) {
      playersByUserId.set(userId, {
        userId,
        type: 'subscriber',
      });
    }
  });

  if (playersByUserId.size === 0) {
    return 'Nenhum jogador registrado';
  }

  return [...playersByUserId.values()]
    .map((player) => {
      const partialReward = player.removedWithReward
        ? ` (parcial: ${player.rewardAmount ?? 0} recompensa(s), ${formatMinutes(player.rewardMinutes ?? 0)})`
        : '';
      return `<@${player.userId}> - ${decodePlayerType(player.type)}${partialReward}`;
    })
    .join('\n');
}

function calculateQuestElapsedTime(quest: Quest) {
  let total = 0;

  if (quest.status === 'finished') {
    total = quest.timeEvents.reduce((acc, ev, i, arr) => {
      if (i === arr.length - 1) return acc;
      if (ev.eventType === 'run') {
        return acc + differenceInSeconds(arr[i + 1].date, ev.date);
      }
      return acc;
    }, 0);
  }

  return Math.floor(total / secondsInMinute);
}

/* ----------------------------------------------------------- */
/* MAIN MISSION EMBED                                          */
/* ----------------------------------------------------------- */

export async function questInfoEmbedMessage({ quest }: { quest: Quest; showQueueList?: boolean }) {
  const { prisma } = require('@/shared/infra/database/prisma');

  const allUserIds = [
    ...(quest.mandatoryPlayers ?? []),
    ...(quest.highPriorityPlayers ?? []),
    ...(quest.questPlayers ?? []).map((p) => p.userId),
  ];

  const uniqueUserIds = [...new Set(allUserIds)].filter(Boolean);
  const fetchedLogs = uniqueUserIds.length > 0 
    ? await prisma.characterLog.findMany({ where: { discordUserId: { in: uniqueUserIds } } })
    : [];

  const logsByUserId = new Map<string, any[]>();
  fetchedLogs.forEach((log: any) => {
    const arr = logsByUserId.get(log.discordUserId) || [];
    arr.push(log);
    logsByUserId.set(log.discordUserId, arr);
  });

  /* ------------------ PLAYER FORMATTER ------------------ */

  function formatPlayer(p: any, fallbackUserId?: string) {
    const id = p.userId || fallbackUserId;
    let name = p.characterName;
    let classe = p.class;
    let nivel = p.level;
    let characterUrl = p.characterUrl;

    if (!classe && id) {
      const userLogs = logsByUserId.get(id) || [];
      const validLogs = userLogs.filter((log: any) => {
        const logRankName = normalizeRankName(log.rankName);
        // Assuming allowedRanks are names or we can just try to match if they match anything in quest ranks
        // Since we don't have guild here to resolve Role ID to Name, we might just pick the first log 
        // Or pick the most relevant log. To keep it simple, pick the first log available.
        return true;
      });

      if (validLogs.length > 0) {
        name = name || validLogs[0].characterName;
        classe = classe || validLogs[0].className;
        nivel = nivel || validLogs[0].level;
        characterUrl = characterUrl || validLogs[0].sheetUrl;
      }
    }

    const nameStr = name ? `**${name}** (<@${id}>)` : `<@${id}>`;
    const classeStr = classe ? `Classe: **${classe}**` : 'Classe: -';
    const nivelStr = nivel ? `Nível: **${nivel}**` : 'Nível: -';
    const fichaStr = characterUrl ? `→ [Ficha](${characterUrl})` : '';

    return `• ${nameStr} — ${classeStr} / ${nivelStr} ${fichaStr}`.trim();
  }

  function normalizeRankName(value: string): string {
    return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  }

  /* ------------------ OBRIGATÓRIOS E PREFERENCIAIS ------------------ */

  const mandatory = quest.mandatoryPlayers?.length
    ? quest.mandatoryPlayers.map(id => formatPlayer({ userId: id }))
    : [];

  let prio: string[];

  if (quest.questPlayers.length > 0) {
    prio = quest.questPlayers
      .filter(p => p.type === 'high-priority' && !p.removedAt)
      .map(p => formatPlayer(p));
  } else {
    prio = quest.highPriorityPlayers?.map(id => formatPlayer({ userId: id })) ?? [];
  }

  /* ------------------ COLAB / NORMAL AFTER PUBLICATION ------------------ */

  const colab = quest.questPlayers
    .filter(p => p.type === 'subscriber' && !p.removedAt)
    .map(p => formatPlayer(p));

  const normal = quest.questPlayers
    .filter(p => p.type === 'normal' && !p.removedAt)
    .map(p => formatPlayer(p));

  const mandatoryField = mandatory.length ? mandatory.join('\n') : '-';
  const prioField = prio.length ? prio.join('\n') : '-';
  const colabField = colab.length ? colab.join('\n') : '-';
  const normalField = normal.length ? normal.join('\n') : '-';

  /* ------------------ PARTICIPATION REQUESTS ------------------ */

  const alreadyDisplayedPlayerIds = new Set([
    ...(quest.mandatoryPlayers ?? []),
    ...(quest.highPriorityPlayers ?? []),
    ...quest.questPlayers.filter((p) => !p.removedAt).map((p) => p.userId)
  ]);

  const pendingRequests = (quest.participationRequests ?? [])
    .filter((req) => !alreadyDisplayedPlayerIds.has(req.userId));

  let requestLines = pendingRequests.map(req => {
    let name = req.characterName;
    if (!name) {
      const userLogs = logsByUserId.get(req.userId) || [];
      if (userLogs.length > 0) {
        name = userLogs[0].characterName;
      }
    }
    const nameStr = name ? `**${name}** (<@${req.userId}>)` : `<@${req.userId}>`;
    const classe = req.class ? `Classe: **${req.class}**` : 'Classe: -';
    const nivel = req.level ? `Nível: **${req.level}**` : 'Nível: -';
    const confirmedIcon = req.confirmedAt ? ' ✅' : '';

    return `• ${nameStr} — ${classe} / ${nivel} → [Ficha](${req.characterUrl})${confirmedIcon}`;
  });

  if (requestLines.length > 15) {
    const extras = requestLines.length - 15;
    requestLines = requestLines.slice(0, 15);
    requestLines.push(`... e mais ${extras} solicitações na fila.`);
  }

  const requestListField = requestLines.length ? requestLines.join('\n') : '-';

  /* ------------------ BASIC INFO ------------------ */

  const allowedRolesList = quest.allowedRanks.map(r => `<@&${r}>`).join('\n');
  const questTags = quest.tags?.length ? quest.tags.join(', ') : '-';
  const formatedQuestDate = formatInBrazil(quest.questDate, 'dd/MM/yyyy HH:mm');
  const totalQuestElapsedTimeInMinutes = calculateQuestElapsedTime(quest);

  const colabSlots = Math.floor(quest.playersAmount / 2);

  const embedMessageData = [
    `**Descrição:**`,
    quest.description,
    ``,
    `🧙‍♂️ **Mestre:** <@${quest.questMaster}>`,
    `⏰ **Data da Missão:** ${formatedQuestDate}`,
    `👥 **Nº Participantes:** ${quest.playersAmount}`,
    ``,
    `👑 **Vagas para Colab:** ${colabSlots}`,
    ``,
    `🎖️ **Ranks Permitidos:**`,
    allowedRolesList,
    ``,
    `🧷 **Obrigatórios:**`,
    mandatoryField,
    ``,
    `🏅 **Prioritários:**`,
    prioField,
    ``,
    `👑 **Colaboradores:**`,
    colabField,
    ``,
    `👤 **Normais:**`,
    normalField,
    ``,
    `🟧 **Solicitações de Participação:**`,
    requestListField,
    ``,
    `📌 **Status:** ${decodeQuestStatus(quest.status)}`,
    `⏰ **Tempo Total:** ${totalQuestElapsedTimeInMinutes} Minutos`,
    `🏷️ **Tags:** ${questTags}`,
    `🔶 **Tipo:** ${quest.type}`,
    `🔗 [Regras](${quest.rules})`,
    `🔗 [Mesa](${quest.tableUrl})`,
    `👤 **Criado por:** <@${quest.createdBy}>`,
  ];

  return new EmbedBuilder()
    .setThumbnail(thumbnails.scroll2)
    .setColor('Random')
    .setTitle(`📜 Missão:\n${quest.name}`)
    .setDescription(embedMessageData.join('\n'))
    .setFooter({ text: String(quest.id) });
}

/* ----------------------------------------------------------- */
/* TIME EVENTS EMBED                                           */
/* ----------------------------------------------------------- */

export function questTimeEventEmbedMessage({
  quest,
  requesterUserId,
}: {
  quest: Quest;
  requesterUserId: string;
}): EmbedBuilder {

  const timeEventsHistory =
    quest.timeEvents.length > 0
      ? quest.timeEvents
          .map((ev) => {
            const d = formatInBrazil(ev.date);
            return `${d} - ${decodeTimeEvent(ev.eventType)} - <@${ev.userId}>`;
          })
          .join('\n')
      : '-';

  return new EmbedBuilder()
    .setThumbnail(thumbnails.stopwatch)
    .setColor('Random')
    .setTitle(`⏲️ Status da Missão Alterado`)
    .setDescription(
      [
        `<@${requesterUserId}> alterou o status da missão`,
        `📜 **Missão:** ${quest.name}`,
        `📌 **Status:** ${decodeQuestStatus(quest.status)}`,
        ``,
        `📑 **Histórico:**`,
        timeEventsHistory,
      ].join('\n')
    );
}

/* ----------------------------------------------------------- */
/* QUEST REWARDS EMBED                                         */
/* ----------------------------------------------------------- */

export async function questRewardEmbedMessage({ quest, guild }: { quest: Quest; guild?: Guild }): Promise<EmbedBuilder> {

  const allowedRolesList = quest.allowedRanks
    .map((r) => `<@&${r}>`)
    .join('\n');

  const selectedPlayersList = buildRewardPlayersList(quest);
  const partialRewardLines = buildPartialRewardLines(quest);

  const totalMinutes = calculateQuestElapsedTime(quest);

  const finalPlayerReward = questRewardAmount(totalMinutes, quest.rewardAventurasOverride);
  let baseMasterReward = Math.floor(totalMinutes / 150) * 100;

  if (quest.rewardAventurasOverride !== undefined && quest.rewardAventurasOverride !== null) {
    baseMasterReward = finalPlayerReward * 100;
  }

  // Calcula o bônus de ranking dedicado do mestre (só vale se a quest tiver EXATAMENTE 1 cargo, sem gambiarras)
  let dedicatedRankBonus = 0;
  const hasOnlyOneRank = quest.allowedRanks.length === 1;
  
  if (hasOnlyOneRank && guild) {
    try {
      const dedicatedRankRepository = container.resolve<IDedicatedRankRepository>('DedicatedRankRepository');
      
      // Tenta achar o ranking que tava ativo quando a quest foi criada
      let dedicatedRank: any = null;
      if (quest.dedicatedRankId) {
        dedicatedRank = await dedicatedRankRepository.findById(quest.dedicatedRankId);
      }
      
      // Se não achou (foi desativado ou a quest é velha), tenta o ranking atual
      if (!dedicatedRank) {
        dedicatedRank = await dedicatedRankRepository.findCurrentByGuildId(guild.id);
      }
      
      if (dedicatedRank) {
        // Busca o cargo da guild pra achar o nome do rank
        const guildRoles = await guild.roles.fetch();
        const rankRoleId = quest.allowedRanks[0];
        const role = guildRoles.get(rankRoleId);
        
        if (role) {
          // Procura o nome do rank na lista de ranks válidos
          const rankInfo = bonfireRpgRankRoles.find(r => r.name === role.name);
          
          if (rankInfo) {
            // Procura esse rank no ranking dedicado pra pegar a recompensa
            const rankReward = dedicatedRank.rankings.find(
              r => r.rankName === rankInfo.name
            );
            
            if (rankReward) {
              // Cálculo: progressoes × bonus por progressão, limitado ao máximo de 3x
              dedicatedRankBonus = Math.min(
                finalPlayerReward * rankReward.rewardPerProgression,
                rankReward.maxTotalReward
              );
            }
          }
        }
      }
    } catch (error) {
      // Se der ruim, finge que não era pra contar mesmo
      dedicatedRankBonus = 0;
    }
  }

  const finalMasterReward = baseMasterReward + dedicatedRankBonus;

  // Verificar se é quest de evento (tag contém "evento", botei lowercase para garantir) e, se for, dar uma recompensa extra de moedas de evento.
  const isEventQuest = quest.tags?.some(tag => tag.toLowerCase() === 'evento') ?? false;
  
  // NOVO SISTEMA DE MOEDAS DE EVENTO:
  // Mestres: 1 moeda de evento para cada 100 moedas de mestre (total, após dedicado)
  const masterEventCoins = isEventQuest ? Math.floor(finalMasterReward / 100) : 0;
  
  // Jogadores: convertem recompensa em braseiros por rank
  let playerBraseirosLines: string[] = [];
  if (isEventQuest && guild) {
    try {
      const guildRoles = await guild.roles.fetch();
      const rankRolesToBraseiros: Record<string, number> = {};
      
      // Mapeia cada cargo permitido pro rank e calcula os braseiros que o pessoal vai ganhar
      for (const roleId of quest.allowedRanks) {
        const role = guildRoles.get(roleId);
        if (role) {
          const rankInfo = bonfireRpgRankRoles.find(r => r.name === role.name);
          if (rankInfo && rankInfo.name in RANK_TO_BRASEIROS) {
            const braseirosPerReward = RANK_TO_BRASEIROS[rankInfo.name as keyof typeof RANK_TO_BRASEIROS];
            const totalBraseiros = finalPlayerReward * braseirosPerReward;
            rankRolesToBraseiros[rankInfo.name] = totalBraseiros;
          }
        }
      }
      
      // Monta as linhas de braseiros pra exibir no embed (já organizado por rank)
      for (const rankRole of bonfireRpgRankRoles) {
        if (rankRole.name in rankRolesToBraseiros) {
          playerBraseirosLines.push(`${rankWithEmoji(rankRole.name)}: ${rankRolesToBraseiros[rankRole.name]} Braseiros🔥`);
        }
      }
    } catch (error) {
      // Se não conseguir puxar os cargos finge q nada aconteceu
    }
  }

  const startDate = formatInBrazil(quest.timeEvents[0].date);
  const endDate = formatInBrazil(quest.timeEvents[quest.timeEvents.length - 1].date);

  const masterRewardLines = dedicatedRankBonus > 0
    ? [
        `${finalMasterReward} Moedas de Mestragem`,
        `_${baseMasterReward} base + ${dedicatedRankBonus} ranque dedicado_`,
      ]
    : [`${finalMasterReward} Moedas de Mestragem`];

  return new EmbedBuilder()
    .setThumbnail(thumbnails.coins)
    .setColor('Random')
    .setTitle(`💎 Recompensas`)
    .setDescription(
      [
        `**Missão:**`,
        quest.name,
        ``,
        `🧙‍♂️ **Mestre:** <@${quest.questMaster}>`,
        `⏰ **Data Inicial:** ${startDate}`,
        `⏰ **Data Final:** ${endDate}`,
        `⏰ **Tempo Total:** ${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m`,
        ``,
        `🎖️ **Ranks:**`,
        allowedRolesList,
        ``,
        `🎫 **Participantes:**`,
        selectedPlayersList,
        ``,
        `🪙 **Recompensa Jogadores:**`,
        `${finalPlayerReward} aventura(s) / ${finalPlayerReward} recompensa(s)`,
        ...(partialRewardLines.length > 0 ? [
          ``,
          `🪙 **Recompensas Parciais:**`,
          ...partialRewardLines,
        ] : []),
        `🪙 **Recompensa Mestre:**`,
        ...masterRewardLines,
        ...(isEventQuest && masterEventCoins > 0 ? [
          ``,
          `🔥 **Moedas de Evento (Mestre):**`,
          `${masterEventCoins} moedas de evento`,
        ] : []),
        ...(isEventQuest && playerBraseirosLines.length > 0 ? [
          ``,
          `🔥 **Braseiros (Jogadores):**`,
          ...playerBraseirosLines,
        ] : []),
        ``,
        `🔗 [FEEDBACK DE MESA](https://docs.google.com/forms/d/e/1FAIpQLScwnTU_3snNOkPFqD3FW82SfDRVxZBiATHnzwr449tW9ZemqQ/viewform)`,
      ].join('\n')
    );
}
