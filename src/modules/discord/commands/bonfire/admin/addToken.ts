import { container } from 'tsyringe';
import { EmbedBuilder } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { Colors } from '@/config/discord';
import { bonfireTokens, bonfireRoles, thumbnails } from '@/config/bonfire';
import { ShowMemberByDiscordUserIdUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdUseCase';
import { CreateMemberUseCase } from '@/modules/members/useCases/CreateMemberUseCase';
import { UpdateMemberUseCase } from '@/modules/members/useCases/UpdateMemberUseCase';

const commandData = new SlashCommandBuilder()
  .setName('token-adicionar')
  .setDescription('🔥 Adiciona uma quantidade de token para um usuário')
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
  )
  .addStringOption((option) => option.setName('email').setDescription('Email').setRequired(false));

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
      const email = interaction.options.getString('email');

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
          if (!email) {
            await interaction.editReply({
              content: `O usuário não possui cadastro, informe o email para prosseguir`,
            });
            return;
          }

          const createMemberUseCase = container.resolve(CreateMemberUseCase);
          const newMember = await createMemberUseCase.execute({
            discordUserId: user.id,
            discordUserTag: user.tag,
            email,
            tokenMission: tokenType === 'missão' ? tokenAmount : 0,
            tokenXpBoost: tokenType === 'boost' ? tokenAmount : 0,
			tokenSuperboost: tokenType === 'superboost' ? tokenAmount : 0,
            isModerator: false,
          });

          const embedMessageData = [
            `<@${user.id}> ganhou ${tokenAmount} token(s) de \`${tokenType}\``,
            ``,
            `Tokens restantes:`,
            `⚔️ **Missão Especial**: ${newMember.tokenMission}`,
            `💥 **Boost**: ${newMember.tokenXpBoost}`,
			`🚀 **Superboost**: ${newMember.tokenSuperboost}`,
          ];

          const embedMessage = new EmbedBuilder()
            .setThumbnail(thumbnails.gift)
            .setColor('Random')
            .setTitle(`🎉 **TOKEN ADICIONADO**`)
            .setDescription(embedMessageData.join('\n'))
            .setTimestamp();

          await interaction.followUp({ embeds: [embedMessage], ephemeral: false });
        }

        if (existingMember) {
          const updateMemberUseCase = container.resolve(UpdateMemberUseCase);

          existingMember.tokenMission =
            tokenType === 'missão'
              ? existingMember.tokenMission + tokenAmount
              : existingMember.tokenMission;

          existingMember.tokenXpBoost =
            tokenType === 'boost'
              ? existingMember.tokenXpBoost + tokenAmount
              : existingMember.tokenXpBoost;
		  
		  existingMember.tokenSuperboost =
            tokenType === 'superboost'
              ? existingMember.tokenSuperboost + tokenAmount
              : existingMember.tokenSuperboost;

          const updatedMember = await updateMemberUseCase.execute(existingMember);

          const embedMessageData = [
            `<@${user.id}> ganhou ${tokenAmount} token(s) de \`${tokenType}\``,
            ``,
            `Tokens restantes:`,
            `⚔️ **Missão Especial**: ${updatedMember.tokenMission}`,
            `💥 **Boost**: ${updatedMember.tokenXpBoost}`,
			`🚀 **Superboost**: ${updatedMember.tokenSuperboost}`,
          ];

          const embedMessage = new EmbedBuilder()
            .setThumbnail(thumbnails.gift)
            .setColor('Random')
            .setTitle(`🎉 **TOKEN ADICIONADO**`)
            .setDescription(embedMessageData.join('\n'))
            .setTimestamp();

          await interaction.followUp({ embeds: [embedMessage], ephemeral: false });
        }
      } catch (error) {
        await interaction.editReply({
          content: `Erro ao tentar presenterar o token:\n${error}`,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
