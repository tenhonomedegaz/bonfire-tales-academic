import { SlashCommandBuilder } from '@discordjs/builders';
import { IDiscordCommand } from '@/modules/discord/types';
import { prisma } from '@/shared/infra/database/prisma';
import { rankWithEmoji } from '@/config/bonfire';

const commandData = new SlashCommandBuilder()
  .setName('meus-logs')
  .setDescription('Mostra todos os seus logs (fichas) cadastrados no bot');

const command: IDiscordCommand = {
  commandData,
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      const logs = await prisma.characterLog.findMany({ where: { discordUserId: interaction.user.id } });

      if (logs.length === 0) {
        await interaction.followUp({
          content: 'Você não tem nenhum log (ficha) cadastrado no sistema.',
          ephemeral: true,
        });
        return;
      }

      const lines = logs.map((log) => {
        return `• **${log.characterName}** (${rankWithEmoji(log.rankName)} - ${log.className}): [Ver Planilha](${log.sheetUrl})`;
      });

      await interaction.followUp({
        content: `**Seus Logs Cadastrados (${logs.length}):**\n\n${lines.join('\n')}`,
        ephemeral: true,
      });
    } catch (error) {
      bot.logger.log('error', 'Erro no comando meus-logs', error);
      await interaction.followUp({
        content: 'Ocorreu um erro ao buscar seus logs.',
        ephemeral: true,
      }).catch(() => null);
    }
  },
};

export default command;
