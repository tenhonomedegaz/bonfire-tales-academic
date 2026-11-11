import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { isBotRootAdmin } from '@/modules/discord/util';
import { registerCharacterLog } from '@/modules/rpg/characterLogs/services/registerCharacterLog';

export const staffRoleNames = [
  bonfireRoles.adminRoleName,
  bonfireRoles.moderatorRoleName,
  'Staff',
  'staff',
];

const commandData = new SlashCommandBuilder()
  .setName('register-log')
  .setDescription('Cadastra o log de personagem de um usuario')
  .addUserOption((option) =>
    option.setName('usuario').setDescription('Usuario dono do log').setRequired(true),
  )
  .addStringOption((option) =>
    option.setName('link').setDescription('Link do Google Sheets do log').setRequired(true),
  );

export function memberHasStaffRole(member: any): boolean {
  return !!member?.roles?.cache?.some((role: any) => staffRoleNames.includes(role.name));
}

const command: IDiscordCommand = {
  commandData,
  allowedRoles: staffRoleNames,
  cooldown: 5000,

  async execute(bot, interaction) {
    await interaction.deferReply({ ephemeral: true });

    if (!isBotRootAdmin(interaction.user.id) && !memberHasStaffRole(interaction.member)) {
      await interaction.editReply({
        content: 'Voce nao tem permissao para usar este comando.',
      });
      return;
    }

    const user = interaction.options.getUser('usuario', true);
    const sheetUrl = interaction.options.getString('link', true);

    try {
      await interaction.editReply('Lendo planilha do log...');

      const { savedLog, isNovice } = await registerCharacterLog({
        discordUserId: user.id,
        discordUserTag: user.tag,
        sheetUrl,
        registeredBy: interaction.user.id,
        allowTransfer: isBotRootAdmin(interaction.user.id),
      });

      await interaction.editReply({
        content: [
          `Log cadastrado para <@${user.id}>.`,
          '',
          `Personagem: **${savedLog.characterName}**`,
          `Rank: **${savedLog.rankName}**`,
          `Classe: **${savedLog.className}**`,
          `Nivel: **${savedLog.level || 'nao identificado'}**`,
          `Aventuras jogadas: **${savedLog.adventuresPlayed}**`,
          `Missoes iniciais validas: **${savedLog.validStarterAdventures}**`,
          `Novato: **${isNovice ? 'sim' : 'nao'}**`,
        ].join('\n'),
      });
    } catch (error: any) {
      bot.logger.log('error', 'register-log failed', error);
      await interaction.editReply({
        content: `Nao foi possivel cadastrar o log:\n\`\`\`\n${error?.message ?? String(error)}\n\`\`\``,
      });
    }
  },
};

export default command;
