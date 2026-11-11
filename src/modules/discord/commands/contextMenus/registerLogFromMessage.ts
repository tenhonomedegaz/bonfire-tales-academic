import { ContextMenuCommandBuilder } from '@discordjs/builders';

import { IDiscordContextMenu, DiscordApplicationCommandTypes } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';
import { memberHasStaffRole } from '@/modules/discord/commands/bonfire/admin/registerLog';
import { registerCharacterLog } from '@/modules/rpg/characterLogs/services/registerCharacterLog';

const commandData = new ContextMenuCommandBuilder()
  .setName('Registrar Log')
  .setType(DiscordApplicationCommandTypes.MESSAGE_CONTEXT);

function extractMentionedUserId(content: string): string | null {
  const match = content.match(/<@!?(\d+)>/);
  return match?.[1] ?? null;
}

function extractGoogleSheetsUrl(content: string): string | null {
  const match = content.match(/https:\/\/docs\.google\.com\/spreadsheets\/d\/[^\s>]+/);
  return match?.[0] ?? null;
}

const command: IDiscordContextMenu = {
  commandData,
  cooldown: 5000,

  async execute(bot, interaction: any) {
    await interaction.deferReply({ ephemeral: true });

    if (!isBotRootAdmin(interaction.user.id) && !memberHasStaffRole(interaction.member)) {
      await interaction.editReply({
        content: 'Voce nao tem permissao para usar este comando.',
      });
      return;
    }

    const targetMessage = interaction.targetMessage;
    const content = targetMessage?.content ?? '';
    const mentionedUserId = extractMentionedUserId(content);
    const sheetUrl = extractGoogleSheetsUrl(content);

    if (!mentionedUserId || !sheetUrl) {
      await interaction.editReply({
        content: 'Nao encontrei uma marcacao de usuario e um link valido do Google Sheets nessa mensagem.',
      });
      return;
    }

    try {
      await interaction.editReply('Lendo mensagem e cadastrando log...');

      const targetUser = await interaction.client.users.fetch(mentionedUserId);
      const { savedLog, isNovice } = await registerCharacterLog({
        discordUserId: targetUser.id,
        discordUserTag: targetUser.tag,
        sheetUrl,
        registeredBy: interaction.user.id,
        allowTransfer: isBotRootAdmin(interaction.user.id),
      });

      await interaction.editReply({
        content: [
          `Log cadastrado para <@${targetUser.id}> a partir da mensagem.`,
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
      bot.logger.log('error', 'register-log context menu failed', error);
      await interaction.editReply({
        content: `Nao foi possivel cadastrar o log:\n\`\`\`\n${error?.message ?? String(error)}\n\`\`\``,
      });
    }
  },
};

export default command;
