/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  Message,
  TextChannel,
  MessageFlags,
} from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';
import { differenceInSeconds, secondsInMinute } from 'date-fns';

import { IDiscordCommand } from '@/modules/discord/types';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { ShowPublishedQuestsUseCase } from '@/modules/rpg/quests/useCases/ShowPublishedQuestsUseCase';
import { questInfoEmbedMessage, questTimeEventEmbedMessage } from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { bonfireChannels, bonfireRoles } from '@/config/bonfire';
import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { hasBotAdminPermission } from '@/modules/discord/util';
import { buildQuestQueueEmbed } from './questQueue';
import { updateQuestEmbeds } from './updateQuestEmbeds';
import { nowInBrazil } from '@/shared/util/dateTime';
import { questRewardAmount } from '@/modules/rpg/quests/services/questReward';



type QuestControlAction = 'painel' | 'adicionar-jogadores' | 'remover-jogador' | 'fila';

const controlQuestCommandData = new SlashCommandBuilder()
  .setName('missao-controles')
  .setDescription('Mostra o painel de controles da missao')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missao').setAutocomplete(true).setRequired(true),
  );

const questQueueCommandData = new SlashCommandBuilder()
  .setName('missao-fila')
  .setDescription('Mostra a fila de inscritos da missao')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missao').setAutocomplete(true).setRequired(true),
  );

const addQuestPlayersCommandData = new SlashCommandBuilder()
  .setName('missao-add-player')
  .setDescription('Adiciona jogadores na missao')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missao').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('jogadores').setDescription('Mencione os jogadores (@jogador1 @jogador2...)').setRequired(true),
  );

const dropQuestPlayerCommandData = new SlashCommandBuilder()
  .setName('missao-drop-player')
  .setDescription('Remove jogadores da missao')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missao').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('jogadores').setDescription('Mencione os jogadores a serem removidos (@jogador1 @jogador2...)').setRequired(true),
  )
  .addBooleanOption((option) =>
    option
      .setName('recompensa')
      .setDescription('Registra recompensa proporcional ao tempo jogado')
      .setRequired(false),
  );

async function resolveQuestFromInput(input: string): Promise<Quest | null> {
  const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
  
  try {
    const questById = await showQuestByIdUseCase.execute(input);
    if (questById) return questById;
  } catch (error) {
    // ID lookup failed, continue to search by name
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

function calculateElapsedUntilNow(quest: Quest): number {
  const events = [...(quest.timeEvents ?? []), { eventType: 'finish' as const, date: nowInBrazil(), userId: 'system' }];

  const totalSeconds = events.reduce((acc, event, index, allEvents) => {
    if (index === allEvents.length - 1) return acc;
    if (event.eventType === 'run') {
      return acc + differenceInSeconds(allEvents[index + 1].date, event.date);
    }
    return acc;
  }, 0);

  return Math.floor(totalSeconds / secondsInMinute);
}

function getActiveQuestPlayers(quest: Quest) {
  return (quest.questPlayers ?? []).filter((player) => !player.removedAt);
}

function createQuestControlCommand(
  currentCommandData: any,
  action: QuestControlAction,
): IDiscordCommand {
  return {
    commandData: currentCommandData,
    allowedRoles: [
      bonfireRoles.masterRoleName,
      bonfireRoles.testMasterRoleName,
      bonfireRoles.adminRoleName,
      bonfireRoles.moderatorRoleName,
    ],
    cooldown: 3 * 1000,

    async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const { user, guild, channel } = interaction;

      if (!guild) {
        await interaction.followUp({ content: 'Não foi possível detectar o servidor do Discord', flags: [MessageFlags.Ephemeral] });
        return;
      }

      if (!channel || !channel.isTextBased()) {
        await interaction.followUp({ content: 'Essa interação só pode ser utilizada em canais de texto', flags: [MessageFlags.Ephemeral] });
        return;
      }

      const textChannel = channel as TextChannel;
      const logChannel = guild.channels.cache.find(
        (guildChannel) => guildChannel.name === bonfireChannels.logChannelName,
      );

      if (!logChannel || !logChannel.isTextBased()) {
        await interaction.editReply({ content: `Canal \`${bonfireChannels.logChannelName}\` inválido` });
        return;
      }

      const questInput = interaction.options.getString('missao', true);
      const quest = await resolveQuestFromInput(questInput);

      if (!quest) {
        await interaction.followUp({
          content: 'Missão não localizada. Se você digitou o nome manualmente, selecione a missão pela lista do autocomplete.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const requesterIsQuestMaster = user.id === quest.questMaster;
      const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
      const requesterIsAdminOrMod =
        memberRoles.includes(bonfireRoles.adminRoleName) ||
        memberRoles.includes(bonfireRoles.moderatorRoleName) ||
        hasBotAdminPermission(user.id, interaction.member);
      const requesterCanModify = requesterIsQuestMaster || requesterIsAdminOrMod;

      if (['adicionar-jogadores', 'remover-jogador', 'fila'].includes(action) && !requesterCanModify) {
        await interaction.followUp({
          content: 'Apenas o mestre da missão ou Admin/Mod pode modificar seus jogadores.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      if (action === 'fila') {
        const queueEmbed = await buildQuestQueueEmbed({ quest, guild });

        const queueControls = new ActionRowBuilder<ButtonBuilder>().addComponents(
          new ButtonBuilder()
            .setCustomId(`queue-confirm:${quest.id}`)
            .setLabel('Confirmar vaga')
            .setStyle(ButtonStyle.Success),
          new ButtonBuilder()
            .setCustomId(`queue-leave:${quest.id}`)
            .setLabel('Desistir da vaga')
            .setStyle(ButtonStyle.Secondary),
        );

        const uniqueUserIds = new Set<string>();
        quest.mandatoryPlayers?.forEach((id) => uniqueUserIds.add(id));
        quest.highPriorityPlayers?.forEach((id) => uniqueUserIds.add(id));
        (quest.participationRequests ?? []).forEach((req) => uniqueUserIds.add(req.userId));

        const mentionsPing = Array.from(uniqueUserIds).map((id) => `<@${id}>`).join(' ');

        const sentMsg = await textChannel.send({
          content: `Fila da missão **${quest.name}**: ${mentionsPing}`,
          embeds: [queueEmbed],
          components: [queueControls],
        });

        if (mentionsPing.length > 0) {
          await sentMsg.edit({ content: `Fila da missão **${quest.name}**:` });
        }

        await interaction.followUp({
          content: 'Fila enviada no canal.',
          flags: [MessageFlags.Ephemeral],
        });

        return;
      }

      if (action === 'adicionar-jogadores') {
        const playersIdsToAdd = new Set<string>();
        const playersString = interaction.options.getString('jogadores', true);
        const extractedIds = playersString.match(/<@!?(\d+)>/g)?.map(m => m.replace(/<@!?/, '').replace('>', '')) || [];
        
        for (const userId of extractedIds) {
          const member = await guild.members.fetch(userId).catch(() => null);
          if (member && !member.user.bot) {
            playersIdsToAdd.add(userId);
          }
        }

        if (playersIdsToAdd.size === 0) {
          await interaction.followUp({ content: 'Nenhum jogador válido mencionado na string.', flags: [MessageFlags.Ephemeral] });
          return;
        }


        const currentQuestPlayersIds = new Set((quest.questPlayers ?? []).filter((player) => !player.removedAt).map((player) => player.userId));
        const addedIds: string[] = [];
        const alreadyInQuestIds: string[] = [];

        quest.questPlayers ??= [];

        playersIdsToAdd.forEach((userId) => {
          if (currentQuestPlayersIds.has(userId)) {
            alreadyInQuestIds.push(userId);
          } else {
            quest.questPlayers.push({ userId, type: 'normal' });
            addedIds.push(userId);
          }
        });

        if (addedIds.length > 0) {
          const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
          await updateQuestUseCase.execute(quest);
          // Atualiza o embed público da missão para que os jogadores recém-adicionados
          // apareçam de imediato (evita a impressão de que o comando não funcionou).
          await updateQuestEmbeds(bot, guild, quest.id).catch(() => null);
        }

        const responseLines: string[] = [];
        if (addedIds.length > 0) {
          responseLines.push(`Jogadores adicionados na missão: ${addedIds.map((id) => `<@${id}>`).join(', ')}.`);
        }
        if (alreadyInQuestIds.length > 0) {
          responseLines.push(`Já estavam na missão: ${alreadyInQuestIds.map((id) => `<@${id}>`).join(', ')}.`);
        }

        await interaction.followUp({
          content: responseLines.join('\n'),
          flags: [MessageFlags.Ephemeral],
        });

        return;
      }

      if (action === 'remover-jogador') {
        const playersString = interaction.options.getString('jogadores', true);
        const targetIds = playersString.match(/<@!?(\d+)>/g)?.map(m => m.replace(/<@!?/, '').replace('>', '')) || [];

        if (targetIds.length === 0) {
          await interaction.followUp({ content: 'Nenhum jogador válido mencionado.', flags: [MessageFlags.Ephemeral] });
          return;
        }

        quest.questPlayers ??= [];
        const applyReward = interaction.options.getBoolean('recompensa') ?? false;
        
        const removedIds: string[] = [];
        const notFoundIds: string[] = [];
        let rewardMinutes = 0;
        let rewardAmount = 0;

        if (applyReward) {
          rewardMinutes = calculateElapsedUntilNow(quest);
          rewardAmount = questRewardAmount(rewardMinutes);
        }

        targetIds.forEach((targetId) => {
          const playerIndex = quest.questPlayers!.findIndex((player) => player.userId === targetId && !player.removedAt);
          if (playerIndex === -1) {
            notFoundIds.push(targetId);
          } else {
            removedIds.push(targetId);
            if (applyReward) {
              quest.questPlayers![playerIndex] = {
                ...quest.questPlayers![playerIndex],
                removedAt: nowInBrazil(),
                removedWithReward: true,
                rewardMinutes,
                rewardAmount,
              };
            } else {
              quest.questPlayers!.splice(playerIndex, 1);
              quest.removedPlayers = [...new Set([...(quest.removedPlayers ?? []), targetId])];
            }
          }
        });

        const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
        await updateQuestUseCase.execute(quest);

        let responseMsg = '';
        if (removedIds.length > 0) {
           const mentions = removedIds.map((id) => `<@${id}>`).join(', ');
           if (applyReward) {
             responseMsg += `Removidos com recompensa parcial (${rewardAmount} recompensa(s) por ${Math.floor(rewardMinutes / 60)}h ${rewardMinutes % 60}m): ${mentions}.\n`;
           } else {
             responseMsg += `Removidos sem recompensa: ${mentions}.\n`;
           }
        }
        if (notFoundIds.length > 0) {
           responseMsg += `Não encontrados ativos na missão: ${notFoundIds.map((id) => `<@${id}>`).join(', ')}.`;
        }

        await interaction.followUp({ content: responseMsg, flags: [MessageFlags.Ephemeral] });
        return;
      }

      const questInfoMessage = await questInfoEmbedMessage({
        quest,
        showQueueList: requesterIsQuestMaster,
      });

      const helperButtons = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId(`quest-help-command:${quest.id}:add`)
          .setLabel('Como adicionar players')
          .setStyle(ButtonStyle.Secondary),
        new ButtonBuilder()
          .setCustomId(`quest-help-command:${quest.id}:drop`)
          .setLabel('Como remover players')
          .setStyle(ButtonStyle.Secondary),
        new ButtonBuilder()
          .setCustomId(`quest-help-command:${quest.id}:queue`)
          .setLabel('Como mandar fila')
          .setStyle(ButtonStyle.Secondary),
      );

      await interaction.followUp({
        content: 'Painel de controle enviado na sala.',
        flags: [MessageFlags.Ephemeral],
      });

      const actions = ['run', 'pause', 'freeze', 'finish'] as const;
      type Action = typeof actions[number];

      const buildControlButton = (action: Action) =>
        new ButtonBuilder()
          .setCustomId(`${action}:${quest.id}`)
          .setLabel(
            action === 'run'
              ? '▶️ Iniciar'
              : action === 'pause'
              ? '⏸️ Pausar'
              : action === 'freeze'
              ? '⏹️ Congelar'
              : '⏏️ Encerrar',
          )
          .setStyle(
            action === 'run'
              ? ButtonStyle.Success
              : action === 'pause'
              ? ButtonStyle.Primary
              : action === 'freeze'
              ? ButtonStyle.Danger
              : ButtonStyle.Secondary,
          );

      const questControlButtons = new ActionRowBuilder<ButtonBuilder>().addComponents(
        buildControlButton('pause'),
        buildControlButton('run'),
        buildControlButton('freeze'),
        buildControlButton('finish'),
      );

      if (requesterCanModify && quest.isPublished) {
        if (quest.status === 'idle') {
          try {
            const activePlayerIds = getActiveQuestPlayers(quest).map((player) => player.userId);
            const legacyPlayerIds = [
              ...(quest.subscribedPlayers ?? []).map((player: any) => (typeof player === 'string' ? player : player.userId)),
              ...(quest.highPriorityPlayers ?? []),
            ];
            const uniqueUserIds = [...new Set([...activePlayerIds, ...legacyPlayerIds].filter(Boolean))];

            if (uniqueUserIds.length > 0) {
              const mentionString = uniqueUserIds.map((id) => `<@${id}>`).join(' ');
              await textChannel.send(`A missão **${quest.name}** está prestes a começar!\nParticipantes: ${mentionString}`);
            }
          } catch (error) {
            bot.logger.log('warn', 'Failed to send start mention message', error);
          }
        }

        let controlMessage: Message | undefined;

        try {
          const questTimeEventMessage = questTimeEventEmbedMessage({
            quest,
            requesterUserId: user.id,
          });

          const sent = await textChannel.send({
            content: null,
            embeds: [questTimeEventMessage],
            components: [questControlButtons],
          });
          controlMessage = sent as Message;
        } catch (error) {
          bot.logger.log('error', 'Failed to send quest control message', error);
          await interaction.followUp({ content: 'Falha ao enviar painel de controle na sala pública.', flags: [MessageFlags.Ephemeral] });
          return;
        }

        if (!controlMessage) {
          await interaction.followUp({ content: 'Não foi possível criar a mensagem de controle.', flags: [MessageFlags.Ephemeral] });
        }
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${currentCommandData.name}`, error);
      await interaction.followUp({
        content: `Não foi possível executar o controle da missão:\n${error}`,
        flags: [MessageFlags.Ephemeral],
      }).catch(() => null);
    }
  },
};
}

export const questQueueCommand = createQuestControlCommand(questQueueCommandData, 'fila');
export const addQuestPlayersCommand = createQuestControlCommand(addQuestPlayersCommandData, 'adicionar-jogadores');
export const dropQuestPlayerCommand = createQuestControlCommand(dropQuestPlayerCommandData, 'remover-jogador');

const command = createQuestControlCommand(controlQuestCommandData, 'painel');

export default command;
