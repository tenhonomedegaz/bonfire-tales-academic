import { EmbedBuilder, Guild, GuildMember } from 'discord.js';

import { bonfireRoles, bonfireRpgRankRoles } from '@/config/bonfire';
import { Quest, ParticipationRequest } from '@/modules/rpg/quests/entities/Quest';
import { getLastPlayedDates } from './getLastPlayedDate';

const OBSIDIANA_RANK_NAME = 'Obsidiana (1-4)';

type QueueCategory =
  | 'mandatory'
  | 'preferential'
  | 'colab'
  | 'normal'
  | 'infrator';

type QueueEntry = {
  userId: string;
  characterName?: string;
  requestDate: Date;
  lastPlayedDate: Date | null;
  category: QueueCategory;
  isColab: boolean;
  isNovato: boolean;
  isInfrator: boolean;
  confirmed: boolean;
  class?: string;
  level?: number;
  characterUrl?: string;
};

type QueueSection = {
  title: string;
  entries: QueueEntry[];
  selectedUserIds?: Set<string>;
};

function sortByLastPlayed(a: QueueEntry, b: QueueEntry) {
  if (!a.lastPlayedDate && b.lastPlayedDate) return -1;
  if (a.lastPlayedDate && !b.lastPlayedDate) return 1;
  if (a.lastPlayedDate && b.lastPlayedDate) {
    const diff = a.lastPlayedDate.getTime() - b.lastPlayedDate.getTime();
    if (diff !== 0) return diff;
  }
  return a.requestDate.getTime() - b.requestDate.getTime();
}

function formatEntryLine(entry: QueueEntry, isSelected: boolean = false): string {
  let marker = '⚪';
  if (entry.isInfrator) marker = '⚫';
  else if (entry.isColab || entry.isNovato) marker = '🟣';

  const tags: string[] = [];
  if (entry.isNovato) tags.push('Novato');
  if (entry.isColab && !entry.isNovato) tags.push('Colab');
  if (entry.isInfrator) tags.push('Infrator');

  const tagText = tags.length ? ` (${tags.join(', ')})` : '';
  const confirmedIcon = entry.confirmed ? '✅ ' : '';

  const nameStr = entry.characterName ? `**${entry.characterName}** (<@${entry.userId}>)` : `<@${entry.userId}>`;
  const userText = isSelected ? `__${nameStr}__` : nameStr;

  const classeStr = entry.class ? `Classe: **${entry.class}**` : 'Classe: -';
  const nivelStr = entry.level ? `Nível: **${entry.level}**` : 'Nível: -';
  const fichaStr = entry.characterUrl ? `→ [Ficha](${entry.characterUrl})` : '';

  const playedStr = entry.lastPlayedDate ? `(Última: <t:${Math.floor(entry.lastPlayedDate.getTime() / 1000)}:R>)` : `(Nunca jogou)`;

  return `${confirmedIcon}${marker} ${userText}${tagText} — ${playedStr} — ${classeStr} / ${nivelStr} ${fichaStr}`;
}

async function fetchMember(guild: Guild, userId: string): Promise<GuildMember | null> {
  const cached = guild.members.cache.get(userId);
  if (cached) return cached;
  return guild.members.fetch(userId).catch(() => null);
}

function shouldUseNovatoAsColab(quest: Quest, guild: Guild): boolean {
  return true; // Todos os novatos tem prioridade de colaborador na fila, independentemente do rank
}

function buildEntryFromRequest({
  request,
  isColab,
  isNovato,
  isInfrator,
  lastPlayedDate,
}: {
  request: ParticipationRequest;
  isColab: boolean;
  isNovato: boolean;
  isInfrator: boolean;
  lastPlayedDate: Date | null;
}): QueueEntry {
  let category: QueueCategory = 'normal';

  if (isInfrator) category = 'infrator';
  else if (isColab) category = 'colab';

  return {
    userId: request.userId,
    characterName: request.characterName,
    requestDate: request.requestDate,
    lastPlayedDate,
    category,
    isColab,
    isNovato,
    isInfrator,
    confirmed: Boolean(request.confirmedAt),
    class: request.class,
    level: request.level,
    characterUrl: request.characterUrl,
  };
}

export async function buildQuestQueueEmbed({
  quest,
  guild,
}: {
  quest: Quest;
  guild: Guild;
}): Promise<EmbedBuilder> {
  const requestMap = new Map<string, ParticipationRequest>();
  (quest.participationRequests ?? []).forEach((req) => {
    requestMap.set(req.userId, req);
  });

  const uniqueUserIds = new Set<string>();
  quest.mandatoryPlayers?.forEach((id) => uniqueUserIds.add(id));
  quest.highPriorityPlayers?.forEach((id) => uniqueUserIds.add(id));
  (quest.participationRequests ?? []).forEach((req) => uniqueUserIds.add(req.userId));

  const { prisma } = require('@/shared/infra/database/prisma');
  const fetchedLogs = uniqueUserIds.size > 0 
    ? await prisma.characterLog.findMany({ where: { discordUserId: { in: Array.from(uniqueUserIds) } } })
    : [];

  const logsByUserId = new Map<string, any[]>();
  fetchedLogs.forEach((log: any) => {
    const arr = logsByUserId.get(log.discordUserId) || [];
    arr.push(log);
    logsByUserId.set(log.discordUserId, arr);
  });

  function getMissingData(userId: string) {
    const userLogs = logsByUserId.get(userId) || [];
    if (userLogs.length > 0) {
      return {
        characterName: userLogs[0].characterName,
        class: userLogs[0].className,
        level: userLogs[0].level,
        characterUrl: userLogs[0].sheetUrl,
      };
    }
    return {};
  }

  const memberMap = new Map<string, GuildMember | null>();
  for (const userId of uniqueUserIds) {
    const member = await fetchMember(guild, userId);
    memberMap.set(userId, member);
  }

  const lastPlayedMap = await getLastPlayedDates(Array.from(uniqueUserIds));

  const useNovatoAsColab = shouldUseNovatoAsColab(quest, guild);

  const mandatoryEntries: QueueEntry[] = (quest.mandatoryPlayers ?? []).map((userId) => {
    const req = requestMap.get(userId);
    return {
      userId,
      characterName: req?.characterName || getMissingData(userId).characterName,
      requestDate: req?.requestDate ?? quest.createdAt,
      lastPlayedDate: lastPlayedMap.get(userId) ?? null,
      category: 'mandatory',
      isColab: false,
      isNovato: false,
      isInfrator: false,
      confirmed: Boolean(req?.confirmedAt),
      class: req?.class || getMissingData(userId).class,
      level: req?.level || getMissingData(userId).level,
      characterUrl: req?.characterUrl || getMissingData(userId).characterUrl,
    };
  });

  const preferentialEntries: QueueEntry[] = (quest.highPriorityPlayers ?? [])
    .filter((userId) => !(quest.mandatoryPlayers ?? []).includes(userId))
    .map((userId) => {
      const req = requestMap.get(userId);
      return {
        userId,
        characterName: req?.characterName || getMissingData(userId).characterName,
        requestDate: req?.requestDate ?? quest.createdAt,
        lastPlayedDate: lastPlayedMap.get(userId) ?? null,
        category: 'preferential',
        isColab: false,
        isNovato: false,
        isInfrator: false,
        confirmed: Boolean(req?.confirmedAt),
        class: req?.class || getMissingData(userId).class,
        level: req?.level || getMissingData(userId).level,
        characterUrl: req?.characterUrl || getMissingData(userId).characterUrl,
      };
    });

  function isObsidianaQuest(quest: Quest, guild: Guild): boolean {
    const allowedNames = quest.allowedRanks
      ?.map((id) => guild.roles.cache.get(id)?.name)
      .filter((name): name is string => Boolean(name)) ?? [];
      
    return allowedNames.length > 0 && allowedNames.every(name => name === OBSIDIANA_RANK_NAME);
  }

  const isObsidiana = isObsidianaQuest(quest, guild);

  const requestEntries: QueueEntry[] = [];

  (quest.participationRequests ?? [])
    .filter((req) => !quest.mandatoryPlayers?.includes(req.userId))
    .filter((req) => !quest.highPriorityPlayers?.includes(req.userId))
    .forEach((request) => {
      const member = memberMap.get(request.userId);
      const roles = member?.roles.cache.map((r) => r.name) ?? [];

      const isInfrator = roles.includes(bonfireRoles.infractorRoleName);
      
      const isColab = !isObsidiana && roles.includes(bonfireRoles.subscriberRoleName);
      const isNovato = roles.includes(bonfireRoles.noviceRoleName);
      const isColabCandidate = isColab || isNovato;

      requestEntries.push(
        buildEntryFromRequest({
          request,
          isColab: isColabCandidate,
          isNovato,
          isInfrator,
          lastPlayedDate: lastPlayedMap.get(request.userId) ?? null,
        }),
      );
    });

  const mandPrefEntries = [...mandatoryEntries, ...preferentialEntries];
  const colabEntries = requestEntries.filter((e) => e.category === 'colab').sort(sortByLastPlayed);
  const normalEntries = requestEntries.filter((e) => e.category === 'normal').sort(sortByLastPlayed);
  const infratorEntries = requestEntries.filter((e) => e.category === 'infrator').sort(sortByLastPlayed);

  const totalSlots = quest.playersAmount;
  const maxColabPool = Math.floor(totalSlots / 2);
  const maxMandPrefColabSlots = Math.floor(totalSlots / 4);

  let slotsToFill = totalSlots;
  const selectedUserIds = new Set<string>();
  const markPicked = (entries: QueueEntry[], count: number) => {
    entries.slice(0, count).forEach((entry) => selectedUserIds.add(entry.userId));
  };

  const mandPrefColabCount = Math.min(mandPrefEntries.length, maxMandPrefColabSlots);
  const leftoverMandPref = mandPrefEntries.slice(mandPrefColabCount);
  markPicked(mandPrefEntries, mandPrefColabCount);
  slotsToFill -= mandPrefColabCount;

  const remainingColabSlots = Math.max(0, maxColabPool - mandPrefColabCount);
  const colabPickedCount = Math.min(colabEntries.length, remainingColabSlots);
  const leftoverColab = colabEntries.slice(colabPickedCount);
  markPicked(colabEntries, colabPickedCount);
  slotsToFill -= colabPickedCount;

  const normalPool = [...leftoverMandPref, ...leftoverColab, ...normalEntries].sort(sortByLastPlayed);
  const normalPickedCount = Math.min(normalPool.length, slotsToFill);
  markPicked(normalPool, normalPickedCount);
  slotsToFill -= normalPickedCount;

  const infratorPickedCount = Math.min(infratorEntries.length, slotsToFill);
  markPicked(infratorEntries, infratorPickedCount);
  slotsToFill -= infratorPickedCount;

  const sections: QueueSection[] = [
    { title: 'Vagas de Prioridade e Obrigatórias', entries: mandPrefEntries, selectedUserIds },
    { title: isObsidiana ? 'Vagas de Novato' : 'Vagas de Colaborador', entries: colabEntries, selectedUserIds },
    { title: 'Vagas Normais', entries: normalEntries, selectedUserIds },
    { title: 'Infratores', entries: infratorEntries, selectedUserIds },
  ];

  const lines: string[] = [];

  sections.forEach((section) => {
    if (section.entries.length === 0) return;

    lines.push(`**${section.title}:**`);
    section.entries.forEach((entry) => {
      const isSelected = section.selectedUserIds?.has(entry.userId) ?? false;
      lines.push(formatEntryLine(entry, isSelected));
    });
    lines.push('');
  });

  if (lines.length === 0) {
    lines.push('Nenhum jogador na fila.');
  }

  const embed = new EmbedBuilder()
    .setColor('Random')
    .setTitle(`Fila da missao: ${quest.name}`)
    .setDescription(lines.join('\n'))
    .setFooter({ text: `Cota Máx Colab/Prioritários: ${maxColabPool} vagas` });

  return embed;
}
