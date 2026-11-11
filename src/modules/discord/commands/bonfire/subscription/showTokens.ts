import { container } from 'tsyringe';
import { EmbedBuilder } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { Colors } from '@/config/discord';
import { ShowMemberByDiscordUserIdUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdUseCase';
import { thumbnails } from '@/config/bonfire';

const commandData = new SlashCommandBuilder()
  .setName('token-info')
  .setDescription('👑 Exibe seus tokens disponíveis');

const command: IDiscordCommand = {
  commandData,
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      const { user } = interaction;
      await interaction.deferReply({ ephemeral: true });

      const showMemberByDiscordUserIdUseCase = container.resolve(ShowMemberByDiscordUserIdUseCase);
      const member = await showMemberByDiscordUserIdUseCase.execute({ discordUserId: user.id });

      if (!member) {
        await interaction.editReply({ content: `Você não possui nenhum token` });
        return;
      }

      const embedMessageData = [
        `⚔️ **Missão Especial**: ${member.tokenMission}`,
        `💥 **Boost**: ${member.tokenXpBoost}`,
        `🚀 **Superboost**: ${member.tokenSuperboost}`,
      ];

      const embedMessage = new EmbedBuilder()
        .setThumbnail(thumbnails.diamond)
        .setColor(Colors.green500)
        .setTitle(`💎 **SEUS TOKENS**`)
        .setDescription(embedMessageData.join('\n'))
        .setTimestamp();

      await interaction.editReply({ embeds: [embedMessage] });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);

      await interaction.editReply({ content: `Erro ao tentar consultar os tokens` });
    }
  },
};

export default command;
