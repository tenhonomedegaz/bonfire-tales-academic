import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';
import { addMinutes, isAfter, isBefore, subMinutes } from 'date-fns';
import { container } from 'tsyringe';

import { bonfireRoles, minMinutesIntervalToCreateQuest } from '@/config/bonfire';
import { IDiscordCommand } from '@/modules/discord/types';
import { hasBotAdminPermission } from '@/modules/discord/util';
import { AutoQuestQueueJob } from '@/modules/rpg/jobs/AutoQuestQueueJob';
import { PublishQuestJob } from '@/modules/rpg/jobs/PublishQuestJob';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';
import { isValidDateFormat, isValidTimeFormat } from '@/shared/util/validators';
import { parseBrazilDateTime } from '@/shared/util/dateTime';
import { updateQuestEmbeds } from './updateQuestEmbeds';

function isValidDate(date: unknown) {
  return date instanceof Date && !Number.isNaN(date.getTime());
}

const commandData = new SlashCommandBuilder()
  .setName('missao-reagendar')
  .setDescription('Reagenda uma missão que ainda não foi iniciada')
  .addStringOption((option) =>
    option.setName('missao').setDescription('Missão').setAutocomplete(true).setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('data-missao').setDescription('Nova data dd/mm/aaaa').setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('hora-missao').setDescription('Nova hora hh:mm').setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
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

      const { user, guild } = interaction;
      if (!guild) {
        await interaction.followUp({ content: 'Servidor não encontrado.' });
        return;
      }

      const questId = interaction.options.getString('missao', true);
      const questDateString = interaction.options.getString('data-missao', true);
      const questTimeString = interaction.options.getString('hora-missao', true);

      if (!isValidDateFormat(questDateString) || !isValidTimeFormat(questTimeString)) {
        await interaction.followUp({ content: 'Use data dd/mm/aaaa e hora hh:mm.' });
        return;
      }

      const newQuestDate = parseBrazilDateTime(questDateString, questTimeString);
      if (!isValidDate(newQuestDate)) {
        await interaction.followUp({ content: 'Nova data inválida.' });
        return;
      }

      const now = interaction.createdAt;
      if (isBefore(newQuestDate, addMinutes(now, minMinutesIntervalToCreateQuest))) {
        await interaction.followUp({ content: `A nova data precisa ser ao menos ${minMinutesIntervalToCreateQuest} minutos no futuro.` });
        return;
      }

      const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
      const quest = await showQuestByIdUseCase.execute(questId);

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
        await interaction.followUp({ content: 'Apenas o mestre da missão ou Admin/Mod pode reagendar.' });
        return;
      }

      if (quest.status !== 'idle') {
        await interaction.followUp({ content: 'Só é possível reagendar missões que ainda não foram iniciadas.' });
        return;
      }

      quest.questDate = newQuestDate;

      const updateQuestUseCase = container.resolve(UpdateQuestUseCase);
      await updateQuestUseCase.execute(quest);
      await updateQuestEmbeds(bot, guild, quest.id);

      await bot.scheduler.cancelJobs?.({ name: AutoQuestQueueJob.jobName, 'data.questId': quest.id });
      await bot.scheduler.cancelJobs?.({ name: PublishQuestJob.jobName, 'data.questId': quest.id });

      if (!quest.isPublished) {
        await bot.scheduler.runJob(PublishQuestJob.jobName, {
          guildId: guild.id,
          questId: quest.id,
          removeJobAfterRun: true,
        });
      }

      const runAutoQueueJobDate = subMinutes(newQuestDate, 20);
      if (isAfter(runAutoQueueJobDate, now)) {
        await bot.scheduler.scheduleJob(AutoQuestQueueJob.jobName, runAutoQueueJobDate, {
          guildId: guild.id,
          questId: quest.id,
          removeJobAfterRun: true,
        });
      }

      await interaction.followUp({ content: `Missão **${quest.name}** reagendada para ${questDateString} ${questTimeString}.` });
    } catch (error) {
      bot.logger.log('error', 'Erro ao rodar /missao-reagendar', error);
      await interaction.followUp({ content: 'Falha ao reagendar a missão.' });
    }
  },
};

export default command;
