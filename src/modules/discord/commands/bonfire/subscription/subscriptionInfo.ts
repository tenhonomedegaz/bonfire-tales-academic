import { SlashCommandBuilder } from '@discordjs/builders';

import { ChannelTypes, IDiscordCommand } from '@/modules/discord/types';
import { createSubscriptionInfoEmbedMessages } from './subscriptionEmbeds';

const commandData = new SlashCommandBuilder()
  .setName('colab-info')
  .setDescription(`👑 Exibe as informações para apoiar o servidor`);

const command: IDiscordCommand = {
  commandData,
  allowedChannelTypes: [ChannelTypes.TEXT],
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      const subscriptionEmbeds = createSubscriptionInfoEmbedMessages({
        discordUserId: interaction.user.id,
        discordUsername: interaction.user.tag,
      });

      const message = [
        `Olá aventureiro!!`,
        `Chegou para colocar lenha na 🔥🔥 fogueira 🔥🔥?`,
        ``,
        `Caso esteja aqui para ajudar pela primeira vez, olhe nossos planos de colaborador para doação.`,
        `Lembramos que o uso do servidor é totalmente gratuito e o dinheiro investido é para a manutenção do próprio, agradecemos imensamente o apoio.`,
      ];

      await interaction.reply({
        content: message.join('\n'),
        embeds: subscriptionEmbeds,
        ephemeral: true,
      });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
