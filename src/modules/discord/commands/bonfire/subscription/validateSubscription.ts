import { container } from 'tsyringe';
import { SlashCommandBuilder } from '@discordjs/builders';

import { EmbedBuilder } from 'discord.js';
import { ChannelTypes, IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles, thumbnails } from '@/config/bonfire';
import { isValidEmail } from '@/shared/util/validators';
import { ShowAllActiveTransactionsByEmailUseCase } from '@/modules/transactions/useCases/ShowAllActiveTransactionsByEmailUseCase';
import { ShowMemberByDiscordUserIdOrEmailUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdOrEmailUseCase';
import { CreateMemberUseCase } from '@/modules/members/useCases/CreateMemberUseCase';
import { ClaimTransactionsTokensUseCase } from '@/modules/transactions/useCases/ClaimTransactionsTokensUseCase';
import { Colors } from '@/config/discord';
import { createSubscriptionInfoEmbedMessages } from './subscriptionEmbeds';

const commandData = new SlashCommandBuilder()
  .setName('colab-liberar')
  .setDescription(
    `👑 Libera o cargo de ${bonfireRoles.subscriberRoleName} com vantagens exclusívas`,
  )
  .addStringOption((option) => option.setName('email').setDescription('Email').setRequired(true));

const command: IDiscordCommand = {
  commandData,
  allowedChannelTypes: [ChannelTypes.TEXT],
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      const { user, guild } = interaction;
      await interaction.deferReply({ ephemeral: true });
      const email = interaction.options.getString('email', true).toLowerCase();

      if (!guild) {
        await interaction.editReply({ content: `Não foi possível detectar o servidor do discord` });
        return;
      }

      if (!isValidEmail(email)) {
        await interaction.editReply({ content: `o email \`${email}\` é inválido` });
        return;
      }

      const guildRoles = await guild.roles.fetch();
      const subscriberRole = guildRoles.find(
        (role) => role.name === bonfireRoles.subscriberRoleName,
      );

      if (!subscriberRole) {
        await interaction.editReply({
          content: `Ocorreu um erro ao tentar validar os benefícios para o email \`${email}\`, por favor verifique se o email está correto.\nSe o problema persistir contate um adiministrador`,
        });
        return;
      }

      try {
        await interaction.editReply({
          content: `aguarde um momento enquanto valido sua assinatura`,
        });

        const showAllActiveTransactionsByEmailUseCase = container.resolve(
          ShowAllActiveTransactionsByEmailUseCase,
        );
        const transactions = await showAllActiveTransactionsByEmailUseCase.execute({
          email,
        });

        if (transactions.length === 0) {
          const subscriptionEmbeds = createSubscriptionInfoEmbedMessages({
            discordUserId: user.id,
            discordUsername: user.tag,
          });

          const message = [
            `Olá aventureiro!!`,
            `Chegou para colocar lenha na 🔥🔥 fogueira 🔥🔥?`,
            ``,
            `Verifiquei aqui e o e-mail \`${email}\` ainda não possui uma assinatura válida, se você fez o pagamento a pouco tempo para colaborar com o servidor aguarde alguns instantes e tente novamente para fazer a liberação.`,
            `Caso esteja aqui para ajudar pela primeira vez, olhe nosso plano de colaborador para doação.`,
            `Lembramos que o uso do servidor é totalmente gratuito e o dinheiro investido é para a manutenção do próprio, agradecemos imensamente o apoio.`,
          ];

          await interaction.followUp({
            content: message.join('\n'),
            embeds: subscriptionEmbeds,
            ephemeral: true,
          });

          return;
        }

        const showMemberByDiscordUserIdOrEmailUseCase = container.resolve(
          ShowMemberByDiscordUserIdOrEmailUseCase,
        );
        const existingMember = await showMemberByDiscordUserIdOrEmailUseCase.execute({
          email,
          discordUserId: user.id,
        });

        if (!existingMember) {
          try {
            const createMemberUseCase = container.resolve(CreateMemberUseCase);
            const newMember = await createMemberUseCase.execute({
              discordUserId: user.id,
              discordUserTag: user.tag,
              email,
              tokenMission: 0,
              tokenXpBoost: 0,
			  tokenSuperboost: 0,
              isModerator: false,
            });

            const discordMember = await interaction.guild?.members.fetch(user.id);
            await discordMember?.roles.add(subscriberRole);

            // update any unclaimed token
            const claimTransactionsTokens = container.resolve(ClaimTransactionsTokensUseCase);
            const memberWithClaimedTokens = await claimTransactionsTokens.execute(newMember);

            await interaction.followUp({
              content: `Parabéns você agora é um colaborador do servidor Bonfire Tales, obrigado por ter colocado lenha na 🔥fogueira🔥.
  Você agora tem acesso a uma fila preferencial para colaboradores.
  Caso tenha optado por ser um colaborardor de nível Marquês/Marquesa ou Duque/Duquesa você receberá tokens para usar no servidor.`,
              ephemeral: true,
            });

            const embedMessageData = [
              `⚔️ **Missão Especial**: ${memberWithClaimedTokens.tokenMission}`,
              `💥 **Boost**: ${memberWithClaimedTokens.tokenXpBoost}`,
            ];

            const embedMessage = new EmbedBuilder()
              .setThumbnail(thumbnails.diamond)
              .setColor(Colors.green500)
              .setTitle(`💎 **SEUS TOKENS**`)
              .setDescription(embedMessageData.join('\n'))
              .setTimestamp();

            await interaction.followUp({ embeds: [embedMessage], ephemeral: true });

            await interaction.followUp({
              content: `*Tokens para missões especiais servem para fazer uma missão agendada com um mestre do jeito que preferir, caso seja um mestre você pode utiliza-la para mestrar para jogadores que escolher, você também pode utilizar esse token para ganhar uma aventura e uma recompensa caso deseje.
*Tokens de boost servem para dobrar a aventura e recompensa da ultima missão que você jogou. (Minimo de 1 por missão.)

  Para utilizar seus tokens avise o mestre e utilize o comando \`token-usar\` no chat da missão que foi utilizado o boost ou a missão especial.
  `,
              ephemeral: true,
            });
          } catch (error) {
            bot.logger.log('error', `Erro ao tentar validar membro ${user.id} - ${email}`, error);

            await interaction.followUp({
              content: `Ocorreu um erro ao tentar validar os dados, por favor tente novamente, se o problema persistir contate um administrador`,
              ephemeral: true,
            });
          }
          return;
        }

        // user registred but not the owner
        if (existingMember.discordUserId !== user.id || existingMember.email !== email) {
          await interaction.followUp({
            content: `O seu usuário do discord já está associado a outro email ou o email \`${email}\` está associado a outro usuário`,
            ephemeral: true,
          });
          return;
        }

        const discordMember = await interaction.guild?.members.fetch(user.id);
        await discordMember?.roles.add(subscriberRole);

        // update any unclaimed token
        const claimTransactionTokens = container.resolve(ClaimTransactionsTokensUseCase);
        await claimTransactionTokens.execute(existingMember);

        await interaction.followUp({
          content: `Parabéns você agora é um colaborador do servidor Bonfire Tales, obrigado por ter colocado lenha na 🔥fogueira🔥.
Você agora tem acesso a uma fila preferencial para colaboradores.
Caso tenha optado por ser um colaborardor de nível Marquês/Marquesa ou Duque/Duquesa você receberá tokens para usar no servidor.`,
          ephemeral: true,
        });

        const embedMessageData = [
          `⚔️ **Missão Especial**: ${existingMember.tokenMission}`,
          `💥 **Boost**: ${existingMember.tokenXpBoost}`,
        ];

        const embedMessage = new EmbedBuilder()
          .setThumbnail(thumbnails.diamond)
          .setColor(Colors.green500)
          .setTitle(`💎 **SEUS TOKENS**`)
          .setDescription(embedMessageData.join('\n'))
          .setTimestamp();

        await interaction.followUp({ embeds: [embedMessage], ephemeral: true });

        await interaction.followUp({
          content: `
*Tokens para missões especiais servem para fazer uma missão agendada com um mestre do jeito que preferir, caso seja um mestre você pode utiliza-la para mestrar para jogadores que escolher, você também pode utilizar esse token para ganhar uma aventura e uma recompensa caso deseje.
*Tokens de boost servem para dobrar a aventura e recompensa da ultima missão que você jogou. (Minimo de 1 por missão.)

Para utilizar seus tokens avise o mestre e utilize o comando \`token-usar\` no chat da missão que foi utilizado o boost ou a missão especial.
`,
          ephemeral: true,
        });
      } catch (error) {
        bot.logger?.log('error', `Erro ao tentar validar membro ${user.id} - ${email}`, error);

        await interaction.followUp({
          content: `Ocorreu um erro ao tentar validar os benefícios para o email \`${email}\`, por favor verifique se o email está correto.\nSe o problema persistir contate um adiministrador`,
          ephemeral: true,
        });
      }
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);
    }
  },
};

export default command;
