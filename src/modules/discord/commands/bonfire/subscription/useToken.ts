import { container } from 'tsyringe';
import ptBR, { format } from 'date-fns';
import { EmbedBuilder } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { Colors } from '@/config/discord';
import { bonfireTokens, bonfireChannels, thumbnails } from '@/config/bonfire';
import { UseMemberTokenUseCase } from '@/modules/members/useCases/UseMemberTokenUseCase';
import { nowInBrazil } from '@/shared/util/dateTime';


const commandData = new SlashCommandBuilder()
  .setName('token-usar')
  .setDescription('👑 Usa o tipo de token especificado')
  .addStringOption((option) => {
    option.setName('tipo-token').setDescription('Selecione o tipo do token').setRequired(true);

    option.addChoices(
      ...bonfireTokens.map((token) => {
        return {
          name: token.name,
          value: token.id,
        };
      }),
    );

    return option;
  });

const command: IDiscordCommand = {
  commandData,
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      const { user } = interaction;
      await interaction.reply({ content: 'Usando Token', ephemeral: true });

      const tokenType = interaction.options.getString('tipo-token', true);

      const logChannel = interaction.guild?.channels.cache.find(
        (channel) => channel.name === bonfireChannels.logChannelName,
      );

      if (!logChannel || !logChannel.isTextBased()) {
        await interaction.editReply({
          content: `Canal \`${bonfireChannels.logChannelName}\` inválido`,
        });
        return;
      }

      try {
        const useMemberTokenUseCase = container.resolve(UseMemberTokenUseCase);
        const updatedMember = await useMemberTokenUseCase.execute({
          discordUserId: user.id,
          tokenType,
        });

        if (!updatedMember) {
          throw new Error('Não foi possível atualizar os tokens');
        }

        // log audit
        const formatedUseDate = format(nowInBrazil(), 'dd/MM/yyyy HH:mm:ss', {
          locale: ptBR,
        });
        await logChannel.send(
          `<@${user.id}> utilizou token de \`${tokenType}\` - ${formatedUseDate}`,
        );

        const embedMessageData = [
          `<@${user.id}> Utilizou token de \`${tokenType}\``,
          ``,
          `Tokens restantes:`,
          `⚔️ **Missão Especial**: ${updatedMember.tokenMission}`,
          `💥 **Boost**: ${updatedMember.tokenXpBoost}`,
		  `🚀 **Superboost**: ${updatedMember.tokenSuperboost}`,
        ];

        const embedMessage = new EmbedBuilder()
          .setThumbnail(thumbnails.tokenStar)
          .setColor('Random')
          .setTitle(`⚔️💥🚀 **TOKEN UTILIZADO**`)
          .setDescription(embedMessageData.join('\n'))
          .setTimestamp();

        await interaction.followUp({ embeds: [embedMessage], ephemeral: false });
      } catch (error) {
        await interaction.editReply({
          content: `Erro ao tentar utilizar o token:\n${error}`,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
