import { SlashCommandBuilder } from '@discordjs/builders';
import { EmbedBuilder } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { prisma } from '@/shared/infra/database/prisma';

const commandData = new SlashCommandBuilder()
  .setName('ver-agendamentos')
  .setDescription('🔍 Lista todas as tarefas agendadas (recorrentes e banco de dados)');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.adminRoleName],
  cooldown: 5000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      const scheduler = bot.scheduler as any;
      const recurringJobs = scheduler?.defaultJobs || [];

      // Fetch one-off jobs from DB
      const dbJobs = await prisma.schedulerJob.findMany({
        orderBy: { nextRunAt: 'asc' },
      });

      const embed = new EmbedBuilder()
        .setTitle('🗓️ Tarefas Agendadas (Schedules)')
        .setColor('#E67E22')
        .setTimestamp();

      const recurringLines = recurringJobs.map((job: any) => {
        const status = job.disabled ? '🔴 Desativado' : '🟢 Ativo';
        return `• **${job.jobName}**\n  Cron: \`${job.cronExpression}\` | Status: ${status}`;
      });

      embed.addFields({
        name: '🔄 Tarefas Recorrentes (Cron)',
        value: recurringLines.join('\n\n') || 'Nenhuma tarefa recorrente registrada.',
      });

      const dbJobsLines = dbJobs.map((job) => {
        const nextRunUnix = Math.floor(job.nextRunAt.getTime() / 1000);
        const dataStr = JSON.stringify(job.data);
        
        let details = '';
        const jobData = (job.data as any) || {};
        if (jobData.userId) {
          details += `Usuário: <@${jobData.userId}> `;
        }
        if (jobData.questId) {
          details += `Missão ID: \`${jobData.questId}\` `;
        }
        if (!details && dataStr !== '{}') {
          details = `Dados: \`${dataStr.slice(0, 50)}\``;
        }

        return `• **${job.name}**\n  Executa em: <t:${nextRunUnix}:F> (<t:${nextRunUnix}:R>)\n  ${details}`;
      });

      const maxFieldLength = 1000;
      let dbValue = '';
      let fieldIndex = 1;

      if (dbJobsLines.length === 0) {
        embed.addFields({
          name: '⏱️ Tarefas Únicas Agendadas (DB)',
          value: 'Nenhuma tarefa única pendente no banco de dados.',
        });
      } else {
        for (const line of dbJobsLines) {
          if (dbValue.length + line.length + 2 > maxFieldLength) {
            embed.addFields({
              name: `⏱️ Tarefas Únicas Agendadas (DB) - Parte ${fieldIndex}`,
              value: dbValue,
            });
            dbValue = '';
            fieldIndex++;
          }
          dbValue += (dbValue ? '\n' : '') + line;
        }
        if (dbValue) {
          embed.addFields({
            name: fieldIndex === 1 ? '⏱️ Tarefas Únicas Agendadas (DB)' : `⏱️ Tarefas Únicas Agendadas (DB) - Parte ${fieldIndex}`,
            value: dbValue,
          });
        }
      }

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      bot.logger.log('error', 'Error listing schedules', error);
      await interaction.editReply({
        content: `Ocorreu um erro ao listar os agendamentos:\n${error}`,
      });
    }
  },
};

export default command;
