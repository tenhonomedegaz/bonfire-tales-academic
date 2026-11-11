import { SlashCommandBuilder } from '@discordjs/builders';

import { env } from '@/shared/env';
import { IDiscordCommand } from '@/modules/discord/types';
import { botRootAdminRoleName } from '@/config/discord';
import { DeployApplicationGuildCommandsUseCase } from '@/modules/discord/useCases/DeployApplicationGuildCommandsUseCase';

const commandData = new SlashCommandBuilder()
  .setName('comandos-sincronizar')
  .setDescription('🤖 Sincroniza os comandos na guild');

function getReadableErrorMessage(error: any): string {
  const rawMessage =
    error?.rawError?.message ||
    error?.message ||
    String(error);

  const validationErrors = error?.rawError?.errors || error?.errors;
  if (!validationErrors) {
    return rawMessage;
  }

  return `${rawMessage}\n${JSON.stringify(validationErrors, null, 2)}`;
}

const command: IDiscordCommand = {
  commandData,
  cooldown: 5 * 1000,
  allowedRoles: [
    botRootAdminRoleName,
    'Mestre',
    'Mestre em Teste',
    'Administração'
  ],
  async execute(bot, interaction) {
    try {
      await interaction.deferReply({ ephemeral: true });

      const discordGuildId = interaction.guild?.id;

      if (!discordGuildId) {
        await interaction.reply({
          content: `Não foi possível indentificar o ID do servidor no discord`,
          ephemeral: true,
        });
        return;
      }

      const deployApplicationGuildCommandsUseCase = new DeployApplicationGuildCommandsUseCase();
      await deployApplicationGuildCommandsUseCase.execute({
        discordClientId: env.DISCORD_CLIENT_ID,
        discordGuildId,
      });

      await interaction.editReply(
        'Comandos sincronizados. As permissoes agora sao validadas pelo bot em runtime.',
      );
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);

      const readableError = getReadableErrorMessage(error);

      await interaction.editReply({
        content: `Erro no comando ${commandData.name}:\n\`\`\`\n${readableError.slice(0, 1800)}\n\`\`\``,
      });
    }
  },
};

export default command;
