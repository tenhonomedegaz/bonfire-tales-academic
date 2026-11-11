// src/modules/discord/events/handlers/handleInteractionButton.ts
import { ButtonInteraction, TextChannel, Message, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
import { container } from 'tsyringe';
import { addHours, format } from 'date-fns';
import ptBR from 'date-fns/locale/pt-BR';

import { IBotEnhanced } from '@/modules/discord/types';
import { DeleteQuestUseCase } from '@/modules/rpg/quests/useCases/DeleteQuestUseCase';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { RegisterQuestTimeEventUseCase } from '@/modules/rpg/quests/useCases/RegisterQuestTimeEventUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import {
  questInfoEmbedMessage,
  questRewardEmbedMessage,
  questTimeEventEmbedMessage,
} from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';
import { AppError } from '@/shared/errors/AppError';
import { bonfireRoles } from '@/config/bonfire';
import { hasBotAdminPermission, findBonfireLogChannel } from '@/modules/discord/util';
import { DeleteSchedulerJobUseCase } from '@/modules/scheduler/useCases/DeleteSchedulerJobUseCase';
import { updateQuestEmbeds } from '@/modules/discord/commands/bonfire/rpg/quests/updateQuestEmbeds';
import { buildQuestQueueEmbed } from '@/modules/discord/commands/bonfire/rpg/quests/questQueue';
import { runQuestInteractionQueued } from '@/modules/rpg/quests/services/questInteractionQueue';
import { ParticipationRequest, Quest } from '@/modules/rpg/quests/entities/Quest';
import { nowInBrazil, formatInBrazil } from '@/shared/util/dateTime';


type ReserveVacancyType = 'normal' | 'subscriber';

function normalizeRankName(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

const processingQuestControls = new Set<string>();
const reserveTimers = new Map<string, NodeJS.Timeout>();
const reserveSkippedByQuest = new Map<string, Set<string>>();



function activeQuestPlayerIds(quest: Quest) {
  return new Set((quest.questPlayers ?? []).filter((player) => !player.removedAt).map((player) => player.userId));
}

async function isColabReserveCandidate(guild: any, userId: string): Promise<boolean> {
  const member = await guild.members.fetch(userId).catch(() => null);
  const roles = member?.roles.cache.map((role: any) => role.name) ?? [];
  return roles.includes(bonfireRoles.subscriberRoleName) || roles.includes(bonfireRoles.noviceRoleName);
}

async function findNextReserveRequest(
  guild: any,
  quest: Quest,
  skippedUserIds = new Set<string>(),
  vacancyType: ReserveVacancyType = 'normal',
): Promise<ParticipationRequest | null> {
  const activeIds = activeQuestPlayerIds(quest);
  const removedIds = new Set(quest.removedPlayers ?? []);
  const ordered = [...(quest.participationRequests ?? [])]
    .filter((request) => request.confirmedAt)
    .sort((a, b) => new Date(a.requestDate).getTime() - new Date(b.requestDate).getTime());

  for (const request of ordered) {
    if (activeIds.has(request.userId) || removedIds.has(request.userId) || skippedUserIds.has(request.userId)) {
      continue;
    }
    if (vacancyType === 'subscriber' && !(await isColabReserveCandidate(guild, request.userId))) {
      continue;
    }
    return request;
  }

  return null;
}

async function inviteNextReserve(
  bot: IBotEnhanced,
  guild: any,
  quest: Quest,
  channel: any,
  vacancyType: ReserveVacancyType = 'normal',
) {
  const skippedUserIds = reserveSkippedByQuest.get(quest.id) ?? new Set<string>();
  const reserve = await findNextReserveRequest(guild, quest, skippedUserIds, vacancyType);
  if (!reserve || !channel?.isTextBased?.()) return;

  const key = `${quest.id}:${reserve.userId}`;
  if (reserveTimers.has(key)) return;

  const row = new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder()
      .setCustomId(`reserve-accept:${quest.id}:${reserve.userId}:${vacancyType}`)
      .setLabel('Aceitar vaga')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId(`reserve-pass:${quest.id}:${reserve.userId}:${vacancyType}`)
      .setLabel('Passar')
      .setStyle(ButtonStyle.Secondary),
  );

  await channel.send({
    content: `<@${reserve.userId}> surgiu uma vaga na missão **${quest.name}**. Você tem 2 minutos para aceitar.`,
    components: [row],
  });

  const timer = setTimeout(async () => {
    reserveTimers.delete(key);
    skippedUserIds.add(reserve.userId);
    reserveSkippedByQuest.set(quest.id, skippedUserIds);
    await channel.send({ content: `<@${reserve.userId}> não respondeu a tempo para **${quest.name}**. Chamando o próximo reserva.` }).catch(() => null);
    const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
    const freshQuest = await showQuestByIdUseCase.execute(quest.id);
    if (freshQuest) await inviteNextReserve(bot, guild, freshQuest, channel, vacancyType);
  }, 2 * 60 * 1000);

  reserveTimers.set(key, timer);
}

export async function handleInteractionButton(bot: IBotEnhanced, interaction: ButtonInteraction) {
  try {
    const { customId, guild, user, message } = interaction;

    if (customId === 'atlas_next' || customId === 'atlas_previous') {
      return;
    }

    try {
      if (!interaction.deferred && !interaction.replied) {
        await interaction.deferUpdate().catch(() => {});
      }
    } catch {
      // ignore - we'll still try to respond later
    }

    // 1) delete-quest:<questId>
    if (customId.startsWith('delete-quest:')) {
      // We want a visible confirmation to pressing user, so reply ephemerally after action
      if (!guild) {
        try {
          await interaction.followUp({ content: 'Erro: não foi possível encontrar o servidor.', ephemeral: true });
        } catch {}
        return;
      }

      const embed = message.embeds[0];
      const questId = embed?.footer?.text;
      if (!questId) {
        try {
          await interaction.followUp({ content: 'Erro: ID da missão não encontrado no embed.', ephemeral: true });
        } catch {}
        return;
      }

      try {
        const deleteQuestUseCase = container.resolve(DeleteQuestUseCase);
        const requesterRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];

        await deleteQuestUseCase.execute({
          requesterUserId: user.id,
          requesterRoles,
          questId,
          discordGuild: guild,
        });

        try {
          await interaction.followUp({ content: 'Missão excluída com sucesso.', ephemeral: true });
        } catch {}

        try {
          if (message.editable) {
            await message.edit({ components: [] });
          }
        } catch {}
      } catch (error) {
        if (error instanceof AppError) {
          try {
            await interaction.followUp({ content: `Erro: ${error.message}`, ephemeral: true });
          } catch {}
          return;
        }
        try {
          await interaction.followUp({ content: 'Ocorreu um erro ao tentar excluir a missão.', ephemeral: true });
        } catch {}
      }

      return;
    }

    if (customId.startsWith('quest-help-command:')) {
      const [, questId, helperAction] = customId.split(':');
      const commandExamples: Record<string, string> = {
        add: `Use:\n\`/missao-add-player missao:${questId} jogadores:@jogador1 @jogador2\``,
        drop: `Use:\n\`/missao-drop-player missao:${questId} jogadores:@jogador1 recompensa:false\`\nMarque \`recompensa:true\` se quiser registrar recompensa parcial.`,
        queue: `Use:\n\`/missao-fila missao:${questId}\``,
      };

      await interaction.followUp({
        content: commandExamples[helperAction] ?? 'Comando nao encontrado.',
        ephemeral: true,
      });
      return;
    }

    // 1.1) quest-join / quest-leave / queue-confirm / queue-leave
    if (
      customId.startsWith('quest-join:') ||
      customId.startsWith('quest-join-char:') ||
      customId.startsWith('quest-leave:') ||
      customId.startsWith('queue-confirm:') ||
      customId.startsWith('queue-leave:') ||
      customId.startsWith('reserve-accept:') ||
      customId.startsWith('reserve-pass:')
    ) {
      if (!guild) {
        try {
          await interaction.followUp({ content: 'Erro: não foi possível encontrar o servidor.', ephemeral: true });
        } catch {}
        return;
      }

      const [action, questId, characterId, vacancyTypeRaw] = customId.split(':');
      const reserveVacancyType: ReserveVacancyType = vacancyTypeRaw === 'subscriber' ? 'subscriber' : 'normal';
      const clickedAt = interaction.createdAt ?? nowInBrazil();

      if (action === 'quest-join' || action === 'quest-join-char') {
        await interaction.followUp({
          content: 'Recebi seu clique e estou colocando sua inscrição na fila. Não precisa clicar de novo.',
          ephemeral: true,
        }).catch(() => null);
      }

      await runQuestInteractionQueued(questId, async () => {

      const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      const quest = await showQuestByIdUseCase.execute(questId);

      if (!quest) {
        try {
          await interaction.followUp({ content: 'Missão não localizada.', ephemeral: true });
        } catch {}
        return;
      }

      if (action === 'reserve-pass') {
        const reserveUserId = characterId;
        if (reserveUserId && reserveUserId !== user.id) {
          await interaction.followUp({ content: 'Essa chamada de reserva não é para você.', ephemeral: true });
          return;
        }

        const key = `${quest.id}:${user.id}`;
        const timer = reserveTimers.get(key);
        if (timer) clearTimeout(timer);
        reserveTimers.delete(key);

        quest.removedPlayers = [...new Set([...(quest.removedPlayers ?? []), user.id])];
        const updatedQuest = await updateQuestUseCase.execute(quest);

        await interaction.followUp({ content: 'Você passou a vaga de reserva.', ephemeral: true });
        await inviteNextReserve(bot, guild, updatedQuest, interaction.channel, reserveVacancyType);
        return;
      }

      if (action === 'reserve-accept') {
        const reserveUserId = characterId;
        if (reserveUserId && reserveUserId !== user.id) {
          await interaction.followUp({ content: 'Essa chamada de reserva não é para você.', ephemeral: true });
          return;
        }

        const request = (quest.participationRequests ?? []).find((req) => req.userId === user.id);
        if (!request) {
          await interaction.followUp({ content: 'Você não está mais na fila dessa missão.', ephemeral: true });
          return;
        }

        const activeIds = activeQuestPlayerIds(quest);
        if (!activeIds.has(user.id) && activeIds.size >= quest.playersAmount) {
          await interaction.followUp({ content: 'Essa vaga já foi preenchida por outro reserva.', ephemeral: true });
          return;
        }

        if (!activeIds.has(user.id)) {
          quest.questPlayers ??= [];
          quest.questPlayers.push({
            userId: user.id,
            type: reserveVacancyType === 'subscriber' ? 'subscriber' : 'fill',
          });
        }

        const updatedQuest = await updateQuestUseCase.execute(quest);
        await updateQuestEmbeds(bot, guild, quest.id);

        const key = `${quest.id}:${user.id}`;
        const timer = reserveTimers.get(key);
        if (timer) clearTimeout(timer);
        reserveTimers.delete(key);


        await interaction.followUp({ content: 'Vaga aceita. Você foi adicionado Ã  missão como reserva.', ephemeral: true });
        return;
      }

      const member = await guild.members.fetch(user.id).catch(() => null);

      if (action === 'quest-join' || action === 'quest-join-char') {
        if (!member) {
          await interaction.followUp({ content: 'Erro ao localizar seu usuário no servidor.', ephemeral: true });
          return;
        }

        const allowedRankNames = quest.allowedRanks
          .map((roleId) => guild.roles.cache.get(roleId)?.name)
          .filter(Boolean) as string[];

        // Usa somente os logs cadastrados. O jogador pode atualizar os dados com /update-logs.
        const findMatchingCharacterLogs = async () => {
          const { prisma } = require('@/shared/infra/database/prisma');
          const characterLogs = await prisma.characterLog.findMany({ where: { discordUserId: user.id } });
          return characterLogs.filter((log: any) => {
            const logRankName = normalizeRankName(log.rankName);

            return allowedRankNames.some((rankName) => {
              const questRankName = normalizeRankName(rankName);
              return logRankName === questRankName ||
                logRankName.includes(questRankName) ||
                questRankName.includes(logRankName);
            });
          });
        };

        let matchingCharacterLogs = await findMatchingCharacterLogs();
        if (matchingCharacterLogs.length === 0) {
          const errorEmbed = new EmbedBuilder()
            .setColor('Red')
            .setTitle('❌ Personagem Inelegível')
            .setDescription('Você não tem registro para o rank desta missão.')
            .addFields(
              {
                name: '🔎 Verificar Personagens',
                value: 'Use o comando\n```/meus-logs```\npara ver se o personagem está cadastrado.',
                inline: true,
              },
              {
                name: '🔄 Atualizar Planilhas',
                value: 'Para atualizar seus dados, use\n```/update-logs```',
                inline: true,
              },
              {
                name: '📝 Caso não tenha log',
                value: 'Chame a **Staff**!\n\n💡 **Tutorial rápido:**\nMarque o cargo **@Staff** e cole o **link da sua planilha** na **mesma mensagem** da marcação.\n*(Isso permite que a Staff use o aplicativo do bot para te registrar rapidamente!)*',
                inline: false,
              }
            );

          await interaction.followUp({
            embeds: [errorEmbed],
            ephemeral: true,
          });
          return;
        }

        let selectedCharacterLog: any;

        if (action === 'quest-join-char') {
          selectedCharacterLog = matchingCharacterLogs.find((log: any) => log.id === characterId);
          if (!selectedCharacterLog) {
            await interaction.followUp({ content: 'Personagem não encontrado ou inválido para esta missão.', ephemeral: true });
            return;
          }
        } else if (matchingCharacterLogs.length > 1) {
          const row = new ActionRowBuilder<any>().addComponents(
            matchingCharacterLogs.slice(0, 5).map((log: any) => 
              new ButtonBuilder()
                .setCustomId(`quest-join-char:${quest.id}:${log.id}`)
                .setLabel(log.characterName)
                .setStyle(ButtonStyle.Primary)
            )
          );
          await interaction.followUp({
            content: 'Você possui mais de um personagem válido para esta missão. Qual deseja inscrever?',
            components: [row],
            ephemeral: true
          });
          return;
        } else {
          selectedCharacterLog = matchingCharacterLogs[0];
        }

        quest.participationRequests ??= [];

        const alreadyRequested = quest.participationRequests.some((req) => req.userId === user.id);
        if (alreadyRequested) {
          if (action === 'quest-join-char' && (interaction.message as Message).editable) {
            await (interaction.message as Message).edit({ components: [] }).catch(() => null);
          }
          await interaction.followUp({ content: 'Você já está na fila dessa missão.', ephemeral: true });
          return;
        }

        quest.participationRequests.push({
          userId: user.id,
          characterName: selectedCharacterLog.characterName,
          characterUrl: selectedCharacterLog.sheetUrl,
          class: selectedCharacterLog.className,
          level: selectedCharacterLog.level,
          requestDate: clickedAt,
          confirmedAt: undefined,
        });

        await updateQuestUseCase.execute(quest);
        await updateQuestEmbeds(bot, guild, quest.id);

        if (action === 'quest-join-char') {
          try {
            if ((interaction.message as Message).editable) {
              await (interaction.message as Message).edit({ components: [] });
            }
          } catch {}
        }

        const successEmbed = new EmbedBuilder()
          .setColor('Green')
          .setTitle('✅ Inscrição Realizada')
          .setDescription(`Solicitação registrada com o personagem **${selectedCharacterLog.characterName}**. Você está na fila da missão.`);

        await interaction.followUp({
          embeds: [successEmbed],
          ephemeral: true,
        });
        return;
      }

      if (action === 'quest-leave' || action === 'queue-leave') {
        const isAttachedToQuest = 
          (quest.questPlayers ?? []).some((player) => player.userId === user.id && !player.removedAt) ||
          (quest.mandatoryPlayers ?? []).includes(user.id) ||
          (quest.highPriorityPlayers ?? []).includes(user.id) ||
          (quest.subscribedPlayers ?? []).some((player) => player.userId === user.id);

        if (isAttachedToQuest && ['running', 'paused', 'frozen'].includes(quest.status)) {
          await interaction.followUp({ content: 'Você não pode desistir da vaga após a missão ter começado.', ephemeral: true });
          return;
        }

        let removed = false;
        const beforeCount = quest.participationRequests?.length ?? 0;

        quest.participationRequests = (quest.participationRequests ?? []).filter(
          (req) => req.userId !== user.id,
        );
        if (quest.participationRequests.length !== beforeCount) removed = true;

        const beforeMandatoryCount = quest.mandatoryPlayers?.length ?? 0;
        const beforePriorityCount = quest.highPriorityPlayers?.length ?? 0;

        quest.mandatoryPlayers = (quest.mandatoryPlayers ?? []).filter((id) => id !== user.id);
        quest.highPriorityPlayers = (quest.highPriorityPlayers ?? []).filter((id) => id !== user.id);

        if ((quest.mandatoryPlayers?.length ?? 0) !== beforeMandatoryCount) removed = true;
        if ((quest.highPriorityPlayers?.length ?? 0) !== beforePriorityCount) removed = true;

        const removedQuestPlayer = (quest.questPlayers ?? []).find((player) => player.userId === user.id && !player.removedAt);
        const removedFromActiveMission = Boolean(removedQuestPlayer);
        if (removedFromActiveMission) {
          quest.questPlayers = (quest.questPlayers ?? []).filter((player) => player.userId !== user.id);
          quest.removedPlayers = [...new Set([...(quest.removedPlayers ?? []), user.id])];
          removed = true;
        }

        if (!removed) {
          await interaction.followUp({ content: 'Você não estava na fila dessa missão.', ephemeral: true });
          return;
        }


        const updatedQuest = await updateQuestUseCase.execute(quest);
        await updateQuestEmbeds(bot, guild, quest.id);

        if (action === 'queue-leave') {
          try {
            const queueEmbed = await buildQuestQueueEmbed({ quest, guild });
            await (interaction.message as Message).edit({ embeds: [queueEmbed] });
          } catch {}
        }

        await interaction.followUp({ content: 'Você desistiu da vaga.', ephemeral: true });

        if (removedFromActiveMission) {
          reserveSkippedByQuest.delete(quest.id);
          const vacancyType: ReserveVacancyType = removedQuestPlayer?.type === 'subscriber' ? 'subscriber' : 'normal';
          await inviteNextReserve(bot, guild, updatedQuest, interaction.channel, vacancyType);
        }
        return;
      }

      if (action === 'queue-confirm') {
        const requestIndex = (quest.participationRequests ?? []).findIndex(
          (req) => req.userId === user.id,
        );

        if (requestIndex === -1) {
          await interaction.followUp({ content: 'Você não está na fila dessa missão.', ephemeral: true });
          return;
        }

        quest.participationRequests[requestIndex] = {
          ...quest.participationRequests[requestIndex],
          confirmedAt: nowInBrazil(),
        };

        await updateQuestUseCase.execute(quest);

        try {
          const queueEmbed = await buildQuestQueueEmbed({ quest, guild });
          await (interaction.message as Message).edit({ embeds: [queueEmbed] });
        } catch {}

        await interaction.followUp({ content: 'Vaga confirmada na fila.', ephemeral: true });
        return;
      }

      });

      return;
    }

    const parts = customId.split(':');
    if (parts.length >= 2) {
      const action = parts[0];
      const questId = parts.slice(1).join(':');

      const validActions = ['run', 'pause', 'freeze', 'finish'];
      if (validActions.includes(action)) {
        if (!guild) {
          try {
            await interaction.followUp({ content: 'Erro: não foi possível encontrar o servidor.', ephemeral: true });
          } catch {}
          return;
        }

        const memberRoles = (interaction.member?.roles as any)?.cache?.map((r: any) => r.name) ?? [];
        const isAdminOrMod =
          memberRoles.includes(bonfireRoles.adminRoleName) ||
          memberRoles.includes(bonfireRoles.moderatorRoleName) ||
          hasBotAdminPermission(user.id, interaction.member);

        try {
          const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
          const quest = await showQuestByIdUseCase.execute(questId);

          if (!quest) {
            try {
              await interaction.followUp({ content: 'Missão não localizada', ephemeral: true });
            } catch {}
            return;
          }

          if (processingQuestControls.has(quest.id)) {
            try {
              await interaction.followUp({ content: '⏳ Processando ação, aguarde...', ephemeral: true });
            } catch {}
            return;
          }
          processingQuestControls.add(quest.id);

          try {
            const requesterIsQuestMaster = quest.questMaster === user.id;
            if (!requesterIsQuestMaster && !isAdminOrMod) {
              try {
                await interaction.followUp({ content: '❌ Você não pode controlar uma missão de outro mestre.', ephemeral: true });
              } catch {}
              return;
            }

            // Register event - PASS guild so baixa role can be applied/removed
            const registerQuestTimeEventUseCase = container.resolve(RegisterQuestTimeEventUseCase);

          const updatedQuest = await registerQuestTimeEventUseCase.execute({
            questId: quest.id,
            requesterUserId: user.id,
            eventType: action as any,
            discordGuild: guild,
          });

          // send time-event embed to quest channel
          const questChannel = guild.channels.cache.find((c) => c.id === updatedQuest.channelId) as TextChannel | undefined;
          if (questChannel && questChannel.isTextBased()) {
            try {
              const questTimeEventMessage = questTimeEventEmbedMessage({
                quest: updatedQuest,
                requesterUserId: user.id,
              });
              await questChannel.send({ content: null, embeds: [questTimeEventMessage] });
            } catch (err) {
              bot.logger.log('warn', 'Failed to send quest time event message to quest channel', err);
            }
          }

          try {
            const build = (act: string) =>
              new ButtonBuilder()
                .setCustomId(`${act}:${updatedQuest.id}`)
                .setLabel(act === 'run' ? '▶️ Iniciar' : act === 'pause' ? '⏸️ Pausar' : act === 'freeze' ? '⏹️ Congelar' : '⏏️ Encerrar')
                .setStyle(act === 'run' ? ButtonStyle.Success : act === 'pause' ? ButtonStyle.Primary : act === 'freeze' ? ButtonStyle.Danger : ButtonStyle.Secondary);

            const newButtonsActionRow = [new ActionRowBuilder<any>().addComponents(build('pause'), build('run'), build('freeze'), build('finish'))];

            if ((message as Message).editable) {
              const newQuestTimeEventMessage = questTimeEventEmbedMessage({
                quest: updatedQuest,
                requesterUserId: user.id,
              });
              await (message as Message).edit({ embeds: [newQuestTimeEventMessage], components: newButtonsActionRow });
            }
          } catch (err) {
            bot.logger.log('warn', 'Could not edit control message after action', err);
          }

          // ephemeral confirmation to user
          try {
            await interaction.followUp({
              content: `Evento "${action}" registrado com sucesso.`,
              ephemeral: true,
            });

            const isFirstRun = action === 'run' && (quest.timeEvents ?? []).filter((e: any) => e.eventType === 'run').length === 0;
            if (isFirstRun && updatedQuest.type === 'Privada') {
              await interaction.followUp({
                content: 'ℹ️  Missão privada iniciada.',
                ephemeral: true,
              });
              return;
            }
          } catch {}

          // if finished -> send reward embed to log channel & quest channel
          if (updatedQuest.status === 'finished') {
            const questReward = await questRewardEmbedMessage({ quest: updatedQuest, guild });
            try {
              if (questChannel && questChannel.isTextBased()) await questChannel.send({ content: null, embeds: [questReward] });
              const logChannel = guild.channels.cache.find((c) => c.name === 'log') as TextChannel | undefined;
              if (logChannel && logChannel.isTextBased()) await logChannel.send({ content: null, embeds: [questReward] });
            } catch (err) {
              bot.logger.log('warn', 'Failed to send reward embed', err);
            }
          }
          } finally {
            processingQuestControls.delete(quest.id);
          }
        } catch (error) {
          if (error instanceof AppError) {
            try {
              await interaction.followUp({ content: `Erro: ${error.message}`, ephemeral: true });
            } catch {}
            return;
          }

          bot.logger.log('error', 'Error handling quest control button', error);
          try {
            await interaction.followUp({ content: 'Erro ao processar ação da missão.', ephemeral: true });
          } catch {}
        }

        return;
      }
    }

    // Fallback for any other buttons not matched above
    try {
      await interaction.followUp({
        content: `âš  Botão "${customId}" não possui handler configurado.`,
        ephemeral: true,
      });
    } catch {}
  } catch (error) {
    // top-level safety
    try {
      await interaction.followUp({ content: 'Ocorreu um erro ao processar o botão.', ephemeral: true });
    } catch {}
    bot.logger.log('error', 'handleInteractionButton', error);
  }
}
