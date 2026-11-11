import { Collection, CommandInteraction } from 'discord.js';

import { IBotEnhanced, IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';
import { hasBotAdminPermission, isBotRootAdmin } from '@/modules/discord/util';

export async function handleInteractionCommand(
  bot: IBotEnhanced,
  interaction: CommandInteraction,
): Promise<void> {
  const { commandName } = interaction;

  const command = bot.commands.get(commandName);

  if (!command) {
    await interaction.reply({
      content: `Comando \`${commandName}\` não reconhecido`,
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

  if ((command as IDiscordCommand).rootAdminOnly && !isBotRootAdmin(interaction.user.id)) {
    await interaction.reply({
      content: 'Voce nao tem permissao para usar esse comando.',
      ephemeral: true,
    });
    return;
  }

  if (command.allowedRoles && command.allowedRoles.length > 0) {
    const member = interaction.member;

    const hasRole = command.allowedRoles.some((role) =>
      (member?.roles as any)?.cache?.has(role) || // role is ID
      (member?.roles as any)?.cache?.some((r: any) => r.name === role) // role is NAME
    );
    const hasBotAdminOverride = hasBotAdminPermission(interaction.user.id, member);

    if (!hasRole && !hasBotAdminOverride) {
      await interaction.reply({
        content: '❌ Você não tem permissão para usar esse comando.',
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
          content: `Espere ${timeLeft.toFixed(1)} segundo(s) antes de reusar o comando \`${command.commandData.name}\``,
          ephemeral: true,
        });

        return;
      }
    }

    timestamps?.set(interaction.user.id, now);

    setTimeout(() => timestamps?.delete(interaction.user.id), cooldownAmount);
  }

  try {
    const guildName = interaction.guild?.name ?? 'DM';
    const channelName = 'name' in (interaction.channel ?? {}) ? (interaction.channel as any).name : 'unknown';
    bot.logger.log(
      'info',
      `Command /${commandName} used by ${interaction.user.tag} (${interaction.user.id}) in ${guildName}/${channelName}`,
    );

    await (command as IDiscordCommand).execute(bot, interaction);
  } catch (error) {
    bot.logger.log('error', `Erro ao tentar executar o comando ${commandName}`, error);

    await interaction.reply({
      content: `Erro ao tentar executar o comando \`${commandName}\` 💣💣!`,
      ephemeral: true,
    });
  }
}
