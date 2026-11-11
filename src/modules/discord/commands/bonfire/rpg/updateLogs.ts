import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { prisma } from '@/shared/infra/database/prisma';
import { registerCharacterLog } from '@/modules/rpg/characterLogs/services/registerCharacterLog';

const commandData = new SlashCommandBuilder()
  .setName('update-logs')
  .setDescription('Atualiza seus logs cadastrados relendo as planilhas do Google Sheets');

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 30000,

  async execute(bot, interaction) {
    await interaction.deferReply({ ephemeral: true });

    try {
      const userLogs = await prisma.characterLog.findMany({ where: { discordUserId: interaction.user.id } });

      if (userLogs.length === 0) {
        await interaction.editReply({ content: 'Voce ainda nao tem nenhum log cadastrado no banco.' });
        return;
      }

      await interaction.editReply({
        content: `Atualizando **${userLogs.length}** log(s)... Isso pode demorar um pouco.`,
      });

      let updated = 0;
      let failed = 0;
      const errors: string[] = [];

      for (const log of userLogs) {
        try {
          await registerCharacterLog({
            discordUserId: interaction.user.id,
            discordUserTag: interaction.user.tag,
            sheetUrl: log.sheetUrl,
            registeredBy: interaction.user.id,
            allowTransfer: false,
          });
          updated++;
        } catch (error: any) {
          failed++;
          const errorMsg = error?.message ?? String(error);
          errors.push(`ERRO **${log.characterName}**: ${errorMsg}`);
        }
      }

      const resultLines = [
        'Atualizacao concluida!',
        '',
        '**Resultado:**',
        `- Atualizados: **${updated}**`,
        `- Falharam: **${failed}**`,
      ];

      if (errors.length > 0) {
        resultLines.push('', '**Erros:**');
        const displayErrors = errors.slice(0, 10);
        resultLines.push(...displayErrors);
        if (errors.length > 10) {
          resultLines.push(`_...e mais ${errors.length - 10} erro(s)._`);
        }
      }

      await interaction.editReply({ content: resultLines.join('\n') });
    } catch (error: any) {
      bot.logger.log('error', 'update-logs failed', error);
      await interaction.editReply({
        content: `Erro ao atualizar logs:\n\`\`\`\n${error?.message ?? String(error)}\n\`\`\``,
      });
    }
  },
};

export default command;
