import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';
import { memberHasStaffRole, staffRoleNames } from './registerLog';

const commandData = new SlashCommandBuilder()
  .setName('remover-log-jogador')
  .setDescription('Remove o log de outro jogador. Uso exclusivo de Staff/Mod/Admin')
  .addUserOption((option) =>
    option.setName('usuario').setDescription('Jogador dono do log').setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('link-planilha').setDescription('Cole o link completo da planilha').setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: staffRoleNames,
  cooldown: 5000,

  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      if (!isBotRootAdmin(interaction.user.id) && !memberHasStaffRole(interaction.member)) {
        await interaction.editReply({ content: 'Voce nao tem permissao para usar este comando.' });
        return;
      }

      const user = interaction.options.getUser('usuario', true);
      const link = interaction.options.getString('link-planilha', true).trim();

      let spreadsheetId = link;
      const urlMatch = link.match(/\/d\/([a-zA-Z0-9-_]+)/);
      if (urlMatch?.[1]) {
        spreadsheetId = urlMatch[1];
      }

      const { prisma } = require('@/shared/infra/database/prisma');
      const log = await prisma.characterLog.findFirst({
        where: {
          discordUserId: user.id,
          OR: [{ sheetUrl: link }, { spreadsheetId }],
        },
      });

      if (!log) {
        await interaction.editReply({
          content: `Nenhum log de <@${user.id}> foi encontrado com esse link. Use \`/ver-logs usuario:@jogador\` para pegar o link exato.`,
        });
        return;
      }

      await prisma.characterLog.delete({ where: { id: log.id } });

      await interaction.editReply({
        content: `OK. O log do personagem **${log.characterName}** pertencente a <@${user.id}> foi removido com sucesso.`,
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando remover-log-jogador', error);
      await interaction.editReply({
        content: 'Ocorreu um erro ao tentar remover o log do jogador.',
      }).catch(() => null);
    }
  },
};

export default command;
