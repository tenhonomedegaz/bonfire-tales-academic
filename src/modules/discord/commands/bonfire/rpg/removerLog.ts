import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
const commandData = new SlashCommandBuilder()
  .setName('remover-log')
  .setDescription('Remove um dos seus logs (fichas) do sistema a partir do link da planilha')
  .addStringOption((option) =>
    option.setName('link-planilha').setDescription('Cole o link completo da sua planilha').setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      const link = interaction.options.getString('link-planilha', true).trim();

      let spreadsheetId = link;
      const urlMatch = link.match(/\/d\/([a-zA-Z0-9-_]+)/);
      if (urlMatch?.[1]) {
        spreadsheetId = urlMatch[1];
      }

      const { prisma } = require('@/shared/infra/database/prisma');
      const log = await prisma.characterLog.findFirst({
        where: {
          discordUserId: interaction.user.id,
          OR: [{ sheetUrl: link }, { spreadsheetId }],
        },
      });

      if (!log) {
        await interaction.followUp({
          content: 'Nenhum log seu foi encontrado com esse link. Use `/meus-logs` para pegar o link exato.',
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      await prisma.characterLog.delete({ where: { id: log.id } });

      await interaction.followUp({
        content: `OK. O log do personagem **${log.characterName}** foi removido dos seus logs com sucesso!`,
        flags: [MessageFlags.Ephemeral],
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando remover-log', error);
      await interaction.followUp({
        content: 'Ocorreu um erro ao tentar remover o log.',
        flags: [MessageFlags.Ephemeral],
      }).catch(() => null);
    }
  },
};

export default command;
