import { Collection, ContextMenuCommandInteraction } from 'discord.js';

import { IBotEnhanced, IDiscordContextMenu } from '@/modules/discord/types';

export async function handleInteractionContextMenu(
  bot: IBotEnhanced,
  interaction: ContextMenuCommandInteraction,
): Promise<void> {
  const { commandName } = interaction;

  const command = bot.commands.get(commandName);

  if (!command) {
    await interaction.reply({
      content: `Comando \`${commandName}\` não localizado`,
      ephemeral: true,
    });
    return;
  }

  // command channels
  if (command.allowedChannelTypes && interaction.channel?.type) {
    if (!command.allowedChannelTypes.includes(interaction.channel.type)) {
      await interaction.reply({
        content: `O comando \`${commandName}\` não pode ser utilizado nesse tipo de chat`,
        ephemeral: true,
      });
      return;
    }
  }

  // discord permissions
  if (command.requiredPermissions) {
    const userPermissions = interaction.member?.permissions as any;

    if (!userPermissions.has(command.requiredPermissions)) {
      await interaction.reply({
        content: `O comando \`${commandName}\` requer permissões para ser executado \`${command.requiredPermissions.join(
          ', ',
        )}\``,
        ephemeral: true,
      });
      return;
    }
  }

  // command delay
  if (command.cooldown) {
    if (!bot.cooldowns?.has(command.commandData.name)) {
      bot.cooldowns?.set(command.commandData.name, new Collection());
    }

    const now = Date.now();

    const timestamps = bot.cooldowns?.get(command.commandData.name);

    const cooldownAmount = command.cooldown || 3 * 1000;

    if (timestamps?.has(interaction.user.id)) {
      const expirationTime = (timestamps.get(interaction.user.id) ?? 0) + cooldownAmount;

      if (now < expirationTime) {
        const timeLeft = (expirationTime - now) / 1000;

        interaction.reply({
          content: `Espere ${timeLeft.toFixed(1)} segundo(s) antes de reusar o comando \`${
            command.commandData.name
          }\``,
          ephemeral: true,
        });

        return;
      }
    }

    timestamps?.set(interaction.user.id, now);

    setTimeout(() => timestamps?.delete(interaction.user.id), cooldownAmount);
  }

  try {
    await (command as IDiscordContextMenu).execute(bot, interaction);
  } catch (error) {
    bot.logger.log('error', `Erro ao tentar executar o comando ${commandName}`, error);

    await interaction.reply({
      content: `Erro ao tentar executar o contexMenu \`${commandName}\` 💣💣!`,
      ephemeral: true,
    });
  }
}
