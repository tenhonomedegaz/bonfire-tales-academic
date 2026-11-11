import { TextChannel } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { ChannelTypes, IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';

const commandData = new SlashCommandBuilder()
  .setName('mensagens-apagar')
  .setDescription(
    '❌ Apaga uma quantidade de mensagens especificadas com data de até 15 dias após seu envio',
  )
  .addIntegerOption((option) =>
    option
      .setName('messages-amount')
      .setDescription('Quantidade de mensagens para apagar (1-100)')
      .setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  cooldown: 3 * 1000,
  allowedRoles: [bonfireRoles.adminRoleName],
  allowedChannelTypes: [ChannelTypes.TEXT],
  async execute(bot, interaction) {
    try {
      const amountOfMessagesToDelete = interaction.options.getInteger('messages-amount');

      if (!amountOfMessagesToDelete || Number.isNaN(amountOfMessagesToDelete)) {
        await interaction.reply({
          content: `A quantidade deve ser entre 1 e 100`,
          ephemeral: true,
        });
        return;
      }

      if (amountOfMessagesToDelete < 1 || amountOfMessagesToDelete > 100) {
        await interaction.reply({
          content: `A quantidade deve ser entre 1 e 100`,
          ephemeral: true,
        });
        return;
      }

      const channel = interaction.channel as TextChannel;

      try {
        await channel.bulkDelete(amountOfMessagesToDelete, true);

        await interaction.reply({
          content: `Deletado ${amountOfMessagesToDelete} mensagens do canal ${channel.name}`,
          ephemeral: true,
        });
      } catch (error) {
        bot.logger.log('error', `Erro no comando ${commandData.name} bulkDelete`, error);

        await interaction.reply({
          content: `Ocorreu um erro ao tentar deletar as mensagens do canal (${channel.name}) - ${error}`,
          ephemeral: true,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
