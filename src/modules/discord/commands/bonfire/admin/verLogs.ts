import { SlashCommandBuilder } from '@discordjs/builders';
import { MessageFlags } from 'discord.js';
import { IDiscordCommand } from '@/modules/discord/types';
import { prisma } from '@/shared/infra/database/prisma';
import { rankWithEmoji } from '@/config/bonfire';
import { isBotRootAdmin } from '@/modules/discord/util';
import { memberHasStaffRole, staffRoleNames } from './registerLog';

const commandData = new SlashCommandBuilder()
  .setName('ver-logs')
  .setDescription('Mostra todos os logs (fichas) cadastrados de um usuário específico')
  .addUserOption((option) =>
    option.setName('usuario').setDescription('Usuário que deseja consultar').setRequired(true)
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: staffRoleNames,
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

      if (!isBotRootAdmin(interaction.user.id) && !memberHasStaffRole(interaction.member)) {
        await interaction.editReply({ content: 'Voce nao tem permissao para usar este comando.' });
        return;
      }

      const targetUser = interaction.options.getUser('usuario', true);
      const logs = await prisma.characterLog.findMany({ where: { discordUserId: targetUser.id } });

      if (logs.length === 0) {
        await interaction.followUp({
          content: `O usuário <@${targetUser.id}> não tem nenhum log (ficha) cadastrado no sistema.`,
          flags: [MessageFlags.Ephemeral],
        });
        return;
      }

      const lines = logs.map((log) => {
        return `• **${log.characterName}** (${rankWithEmoji(log.rankName)} - ${log.className}): [Ver Planilha](${log.sheetUrl})`;
      });

      await interaction.followUp({
        content: `**Logs Cadastrados de <@${targetUser.id}> (${logs.length}):**\n\n${lines.join('\n')}`,
        flags: [MessageFlags.Ephemeral],
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando ver-logs', error);
      await interaction.followUp({
        content: 'Ocorreu um erro ao buscar os logs do usuário.',
        flags: [MessageFlags.Ephemeral],
      }).catch(() => null);
    }
  },
};

export default command;
