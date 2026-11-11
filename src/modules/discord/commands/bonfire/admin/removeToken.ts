import { container } from 'tsyringe';
import { EmbedBuilder } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { Colors } from '@/config/discord';
import { bonfireTokens, bonfireRoles, thumbnails } from '@/config/bonfire';
import { ShowMemberByDiscordUserIdUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdUseCase';
import { UpdateMemberUseCase } from '@/modules/members/useCases/UpdateMemberUseCase';

const commandData = new SlashCommandBuilder()
  .setName('token-remover')
  .setDescription('🔥 Remove uma quantidade de token para um usuário')
  .addUserOption((option) =>
    option.setName('usuario').setDescription('Selecione um usuário').setRequired(true),
  )
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
  })
  .addIntegerOption((option) =>
    option.setName('quantidade-tokens').setDescription('Quantidade de tokens').setRequired(true),
  );

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.adminRoleName],
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      await interaction.reply({ content: 'gerando tokens', ephemeral: true });

      const user = interaction.options.getUser('usuario', true);
      const tokenType = interaction.options.getString('tipo-token', true);
      const tokenAmount = interaction.options.getInteger('quantidade-tokens', true);

      try {
        if (tokenAmount <= 0 || tokenAmount > 10) {
          await interaction.editReply({
            content: `Quantidade de tokens inválida`,
          });
          return;
        }

        const showMemberByDiscordUserIdUseCase = container.resolve(
          ShowMemberByDiscordUserIdUseCase,
        );
        const existingMember = await showMemberByDiscordUserIdUseCase.execute({
          discordUserId: user.id,
        });

        if (!existingMember) {
          await interaction.editReply({
            content: `O usuário não possui cadastro`,
          });
          return;
        }

        existingMember.tokenMission =
          tokenType === 'missão'
            ? existingMember.tokenMission - tokenAmount
            : existingMember.tokenMission;

        existingMember.tokenXpBoost =
          tokenType === 'boost'
            ? existingMember.tokenXpBoost - tokenAmount
            : existingMember.tokenXpBoost;

        existingMember.tokenSuperboost =
          tokenType === 'superboost'
            ? existingMember.tokenSuperboost - tokenAmount
            : existingMember.tokenSuperboost;

        if (existingMember.tokenMission < 0 || existingMember.tokenXpBoost < 0 || existingMember.tokenSuperboost < 0) {
          await interaction.editReply({
            content: `O usuário não possui quantidade suficiente de tokens para serem removidos`,
          });
          return;
        }

        const updateMemberUseCase = container.resolve(UpdateMemberUseCase);
        const updatedMember = await updateMemberUseCase.execute(existingMember);

        const embedMessageData = [
          `<@${user.id}> perdeu ${tokenAmount} token(s) de \`${tokenType}\``,
          ``,
          `Tokens restantes:`,
          `⚔️ **Missão Especial**: ${updatedMember.tokenMission}`,
          `💥 **Boost**: ${updatedMember.tokenXpBoost}`,
		  `🚀 **Superboost**: ${updatedMember.tokenSuperboost}`,
        ];

        const embedMessage = new EmbedBuilder()
          .setThumbnail(thumbnails.tokens)
          .setColor('Random')
          .setTitle(`🎟️ **TOKEN REMOVIDO** 🎟️`)
          .setDescription(embedMessageData.join('\n'))
          .setTimestamp();

        await interaction.followUp({ embeds: [embedMessage], ephemeral: false });
      } catch (error) {
        await interaction.editReply({
          content: `Erro ao tentar remover o token:\n${error}`,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
