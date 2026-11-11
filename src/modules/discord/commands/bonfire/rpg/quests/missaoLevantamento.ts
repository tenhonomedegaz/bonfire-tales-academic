import { SlashCommandBuilder } from '@discordjs/builders';
import { EmbedBuilder } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { prisma } from '@/shared/infra/database/prisma';

const commandData = new SlashCommandBuilder()
  .setName('missao-levantamento')
  .setDescription('📊 Levantamento do número de missões criadas por cada mestre');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [
    bonfireRoles.adminRoleName,
    bonfireRoles.moderatorRoleName,
    bonfireRoles.masterRoleName,
    bonfireRoles.testMasterRoleName,
  ],
  cooldown: 5000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      // Agrupa e conta as missões por mestre no banco
      const questMasterGroups = await prisma.quest.groupBy({
        by: ['questMaster'],
        _count: {
          id: true,
        },
      });

      if (questMasterGroups.length === 0) {
        await interaction.editReply({
          content: 'Nenhuma missão registrada no banco de dados.',
        });
        return;
      }

      // Ordena por quantidade decrescente
      const sortedGroups = questMasterGroups.sort(
        (a, b) => (b._count.id || 0) - (a._count.id || 0)
      );

      const embed = new EmbedBuilder()
        .setTitle('📊 Levantamento de Missões por Mestre')
        .setColor('#8B5CF6')
        .setTimestamp();

      const lines = sortedGroups.map((group, index) => {
        const mestreMention = `<@${group.questMaster}>`;
        const count = group._count.id;
        const medal = index === 0 ? '🥇 ' : index === 1 ? '🥈 ' : index === 2 ? '🥉 ' : '• ';
        return `${medal}${mestreMention}: **${count}** ${count === 1 ? 'missão' : 'missões'}`;
      });

      const maxFieldLength = 4096;
      let description = '';
      let parts: string[] = [];

      for (const line of lines) {
        if (description.length + line.length + 2 > maxFieldLength) {
          parts.push(description);
          description = '';
        }
        description += (description ? '\n' : '') + line;
      }
      if (description) {
        parts.push(description);
      }

      embed.setDescription(parts[0]);

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      bot.logger.log('error', 'Error in missao-levantamento command', error);
      await interaction.editReply({
        content: `Ocorreu um erro ao realizar o levantamento:\n${error}`,
      });
    }
  },
};

export default command;
