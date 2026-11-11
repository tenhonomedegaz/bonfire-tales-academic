import { SlashCommandBuilder } from '@discordjs/builders';
import { EmbedBuilder, Guild, GuildMember, TextChannel, MessageFlags } from 'discord.js';
import { container } from 'tsyringe';

import { IDiscordCommand } from '@/modules/discord/types';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { bonfireRoles } from '@/config/bonfire';
import { Quest, ParticipationRequest } from '@/modules/rpg/quests/entities/Quest';
import { hasBotAdminPermission } from '@/modules/discord/util';
import { getLastPlayedDates } from './getLastPlayedDate';

const OBSIDIANA_RANK_NAME = 'Obsidiana (1-4)';

type PickedPlayer = {
  userId: string;
  type: 'normal' | 'high-priority' | 'subscriber' | 'fill';
};

const commandData = new SlashCommandBuilder()
  .setName('missao-pick')
  .setDescription('Seleciona automaticamente os jogadores confirmados da fila para a missão')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missão').setAutocomplete(true).setRequired(true),
  );

async function fetchMember(guild: Guild, userId: string): Promise<GuildMember | null> {
  const cached = guild.members.cache.get(userId);
  if (cached) return cached;
  return guild.members.fetch(userId).catch(() => null);
}

function isObsidianaQuest(quest: Quest, guild: Guild): boolean {
  const allowedNames = quest.allowedRanks
    ?.map((id) => guild.roles.cache.get(id)?.name)
    .filter((name): name is string => Boolean(name)) ?? [];
    
  return allowedNames.length > 0 && allowedNames.every(name => name === OBSIDIANA_RANK_NAME);
}

const objectIdRegex = /^(?:[a-f\d]{24}|c[a-z0-9]{24})$/i;

async function resolveQuestFromInput(input: string): Promise<Quest | null> {
  if (objectIdRegex.test(input)) {
    const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
    return showQuestByIdUseCase.execute(input);
  }

  const showPublishedQuestsUseCase = container.resolve(ShowPublishedQuestsUseCase);
  const quests = await showPublishedQuestsUseCase.execute({
    searchTerm: input,
    limit: 25,
  });

  const normalizedInput = input.trim().toLowerCase();

  return (
    quests.find((quest) => quest.name.toLowerCase() === normalizedInput) ||
    quests.find((quest) => quest.name.toLowerCase().includes(normalizedInput)) ||
    null
  );
}

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [
    bonfireRoles.masterRoleName,
    bonfireRoles.testMasterRoleName,
    bonfireRoles.adminRoleName,
    bonfireRoles.moderatorRoleName,
  ],
  cooldown: 5 * 1000,
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const { user, guild } = interaction;
      if (!guild) {
        await interaction.followUp({ content: 'Servidor não encontrado.' });
        return;
      }

      const questInput = interaction.options.getString('missao', true);
      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({ content: 'Missão não encontrada.' });
        return;
      }

      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterCanModify =
        user.id === quest.questMaster ||
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        memberRoles.includes(bonfireRoles.moderatorRoleName) ||
        hasBotAdminPermission(user.id, interaction.member);

      if (!requesterCanModify) {
        await interaction.followUp({ content: 'Apenas o mestre da missão ou Admin/Mod pode rodar o pick.' });
        return;
      }

      if (quest.status !== 'idle') {
        await interaction.followUp({ content: 'Não é possível fazer pick numa missão em andamento ou finalizada.' });
        return;
      }

      const isObsidiana = isObsidianaQuest(quest, guild);

      // Obter apenas os confirmados
      const confirmedRequests = (quest.participationRequests ?? []).filter((req) => req.confirmedAt);
      
      const requestMap = new Map<string, ParticipationRequest>();
      confirmedRequests.forEach((req) => {
        requestMap.set(req.userId, req);
      });

      // Mapeamento dos membros e roles
      const uniqueUserIds = new Set<string>();
      quest.mandatoryPlayers?.forEach((id) => uniqueUserIds.add(id));
      quest.highPriorityPlayers?.forEach((id) => uniqueUserIds.add(id));
      confirmedRequests.forEach((req) => uniqueUserIds.add(req.userId));

      const memberMap = new Map<string, GuildMember | null>();
      for (const userId of uniqueUserIds) {
        const member = await fetchMember(guild, userId);
        memberMap.set(userId, member);
      }

      const lastPlayedMap = await getLastPlayedDates(Array.from(uniqueUserIds));

      type QueueEntry = { userId: string; req: ParticipationRequest | undefined; lastPlayedDate: Date | null };

      // Arrays para cada categoria
      const mandatoryEntries: QueueEntry[] = [];
      const preferentialEntries: QueueEntry[] = [];
      const colabEntries: QueueEntry[] = [];
      const normalEntries: QueueEntry[] = [];
      const infratorEntries: QueueEntry[] = [];

      // Popula obrigatórios e preferenciais (apenas confirmados)
      (quest.mandatoryPlayers ?? []).forEach((userId) => {
        const req = requestMap.get(userId);
        if (req) mandatoryEntries.push({ userId, req, lastPlayedDate: lastPlayedMap.get(userId) ?? null });
      });

      (quest.highPriorityPlayers ?? []).forEach((userId) => {
        if (quest.mandatoryPlayers?.includes(userId)) return;
        const req = requestMap.get(userId);
        if (req) preferentialEntries.push({ userId, req, lastPlayedDate: lastPlayedMap.get(userId) ?? null });
      });

      // Popula os demais
      confirmedRequests.forEach((request) => {
        if (quest.mandatoryPlayers?.includes(request.userId)) return;
        if (quest.highPriorityPlayers?.includes(request.userId)) return;

        const member = memberMap.get(request.userId);
        const roles = member?.roles.cache.map((r) => r.name) ?? [];

        const isInfrator = roles.includes(bonfireRoles.infractorRoleName);
        
        const isColab = !isObsidiana && roles.includes(bonfireRoles.subscriberRoleName);
        const isNovato = roles.includes(bonfireRoles.noviceRoleName);
        const isColabCandidate = isColab || isNovato;

        const entry: QueueEntry = { userId: request.userId, req: request, lastPlayedDate: lastPlayedMap.get(request.userId) ?? null };

        if (isInfrator) infratorEntries.push(entry);
        else if (isColabCandidate) colabEntries.push(entry);
        else normalEntries.push(entry);
      });

      const sortByLastPlayed = (a: QueueEntry, b: QueueEntry) => {
        if (!a.lastPlayedDate && b.lastPlayedDate) return -1;
        if (a.lastPlayedDate && !b.lastPlayedDate) return 1;
        if (a.lastPlayedDate && b.lastPlayedDate) {
          const diff = a.lastPlayedDate.getTime() - b.lastPlayedDate.getTime();
          if (diff !== 0) return diff;
        }
        return (a.req?.requestDate.getTime() ?? 0) - (b.req?.requestDate.getTime() ?? 0);
      };

      colabEntries.sort(sortByLastPlayed);
      normalEntries.sort(sortByLastPlayed);
      infratorEntries.sort(sortByLastPlayed);

      // === ALGORITMO DE SELEÇÃO ===
      let slotsToFill = quest.playersAmount;
      const pickedPlayers: PickedPlayer[] = [];
      
      const pushPicked = (userId: string, type: PickedPlayer['type']) => {
        if (slotsToFill > 0) {
          pickedPlayers.push({ userId, type });
          slotsToFill--;
        }
      };

      const mandPrefEntries = [...mandatoryEntries, ...preferentialEntries];
      const maxColabPool = Math.floor(quest.playersAmount / 2);
      const maxMandPrefColabSlots = Math.floor(quest.playersAmount / 4);

      // 1. Mand/Pref (Cota: maxMandPrefColabSlots)
      const mandPrefColabCount = Math.min(mandPrefEntries.length, maxMandPrefColabSlots);
      const pickedMandPrefColab = mandPrefEntries.slice(0, mandPrefColabCount);
      const leftoverMandPref = mandPrefEntries.slice(mandPrefColabCount);
      pickedMandPrefColab.forEach(entry => pushPicked(entry.userId, 'high-priority'));

      // 2. Colab (Cota: maxColabPool - mandPrefColabCount)
      const remainingColabSlots = Math.max(0, maxColabPool - mandPrefColabCount);
      const colabPickedCount = Math.min(colabEntries.length, remainingColabSlots);
      const pickedColab = colabEntries.slice(0, colabPickedCount);
      const leftoverColab = colabEntries.slice(colabPickedCount);
      pickedColab.forEach(entry => pushPicked(entry.userId, 'subscriber'));

      // 3. Normal (ampla concorrencia por ordem de inscricao/ultima jogada)
      const normalPool = [...leftoverMandPref, ...leftoverColab, ...normalEntries].sort(sortByLastPlayed);
      normalPool.forEach(entry => pushPicked(entry.userId, 'normal'));

      // 4. Infratores
      infratorEntries.forEach(entry => pushPicked(entry.userId, 'normal'));

      // Adicionar os selecionados no questPlayers (preservando quem já estava lá)
      quest.questPlayers ??= [];
      const currentQuestPlayersIds = new Set(quest.questPlayers.map((player) => player.userId));
      const newlyAdded: string[] = [];

      pickedPlayers.forEach(({ userId, type }) => {
        if (!currentQuestPlayersIds.has(userId)) {
          const request = requestMap.get(userId);
          quest.questPlayers!.push({
            userId,
            type,
          });
          newlyAdded.push(userId);
        }
      });

      if (newlyAdded.length > 0) {
        const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
        await updateQuestUseCase.execute(quest);

        const mentionsList = newlyAdded.map((id) => `- <@${id}>`).join('\n');
        const mentionsPing = newlyAdded.map((id) => `<@${id}>`).join(' ');

        const embed = new EmbedBuilder()
          .setColor('Green')
          .setTitle('🎲 Seleção Automática de Jogadores')
          .setDescription(`Os seguintes jogadores foram selecionados da fila para a missão **${quest.name}** e confirmados:\n\n${mentionsList}`)
          .setFooter({ text: `${pickedPlayers.length}/${quest.playersAmount} vagas preenchidas via pick.` });

        const channel = interaction.channel as TextChannel;
        if (channel && channel.isTextBased()) {
          await channel.send({ content: mentionsPing, embeds: [embed] });
        }

        await interaction.followUp({ content: 'Seleção automática concluída com sucesso!' });
      } else {
        await interaction.followUp({ content: 'A seleção rodou, mas nenhum jogador novo foi adicionado (vagas esgotadas ou jogadores já estavam na missão).' });
      }

    } catch (error) {
      bot.logger.log('error', 'Erro ao rodar /missao-pick', error);
      await interaction.followUp({ content: 'Falha ao executar o auto-pick.' });
    }
  },
};

export default command;
