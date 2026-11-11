import { container } from 'tsyringe';
import ptBR, { format } from 'date-fns';
import { EmbedBuilder } from 'discord.js';
import { SlashCommandBuilder } from '@discordjs/builders';

import { IDiscordCommand } from '@/modules/discord/types';
import { Colors } from '@/config/discord';
import { ShowMemberByDiscordUserIdUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdUseCase';
import { ShowAllActiveTransactionsByEmailUseCase } from '@/modules/transactions/useCases/ShowAllActiveTransactionsByEmailUseCase';
import { bonfireRoles, thumbnails } from '@/config/bonfire';

const commandData = new SlashCommandBuilder()
  .setName('colab')
  .setDescription('Exibe suas colaborações com tempo ativo');

const command: IDiscordCommand = {
  commandData,
  cooldown: 3 * 1000,
  async execute(bot, interaction) {
    try {
      const { user } = interaction;
      await interaction.deferReply({ ephemeral: true });

      const memberRoles = (interaction.member?.roles as any)?.cache;
      const hasAdminRole = memberRoles?.some(
        (role: any) => role.name === bonfireRoles.adminRoleName,
      );
      const hasModeratorRole = memberRoles?.some(
        (role: any) => role.name === bonfireRoles.moderatorRoleName,
      );

      if (hasAdminRole || hasModeratorRole) {
        const benefitType = hasAdminRole ? 'administração' : 'moderação';
        const embedMessage = new EmbedBuilder()
          .setThumbnail(thumbnails.crown)
          .setColor(Colors.green500)
          .setTitle('COLABORAÇÕES ATIVAS')
          .addFields(
            { name: 'Tipo Colaboração', value: '\u200B', inline: true },
            { name: 'Data Pagamento', value: '\u200B', inline: true },
            { name: 'Data Expiração', value: '\u200B', inline: true },
            {
              name: '\u200B',
              value: `Duque exclusivo de ${benefitType} (equivalente ao plano de R$39,90)`,
              inline: true,
            },
            { name: '\u200B', value: `Benefício de ${benefitType}`, inline: true },
            { name: '\u200B', value: 'Vitalício enquanto mantiver o cargo', inline: true },
          )
          .setTimestamp();

        await interaction.editReply({ embeds: [embedMessage] });
        return;
      }

      const showMemberByDiscordUserIdUseCase = container.resolve(ShowMemberByDiscordUserIdUseCase);
      const member = await showMemberByDiscordUserIdUseCase.execute({ discordUserId: user.id });

      if (!member) {
        await interaction.editReply({ content: 'Você não possui nenhuma colaboração' });
        return;
      }

      const showAllActiveTransactionsByEmailUseCase = container.resolve(
        ShowAllActiveTransactionsByEmailUseCase,
      );
      const transactions = await showAllActiveTransactionsByEmailUseCase.execute({
        email: member.email,
      });

      if (transactions.length === 0) {
        await interaction.editReply({ content: 'Você não possui nenhuma colaboração ativa' });
        return;
      }

      const embedMessage = new EmbedBuilder()
        .setThumbnail(thumbnails.crown)
        .setColor(Colors.green500)
        .setTitle('COLABORAÇÕES ATIVAS')
        .setTimestamp();

      embedMessage.addFields(
        { name: 'Tipo Colaboração', value: '\u200B', inline: true },
        { name: 'Data Pagamento', value: '\u200B', inline: true },
        { name: 'Data Expiração', value: '\u200B', inline: true },
      );

      transactions.forEach((transaction) => {
        const formatedPaymentDate = format(transaction.paymentDate, 'dd/MM/yyyy', {
          locale: ptBR,
        });

        const formatedExpirationDate = format(transaction.expirationDate, 'dd/MM/yyyy', {
          locale: ptBR,
        });

        embedMessage.addFields(
          { name: '\u200B', value: transaction.subscriptionPlan || '-', inline: true },
          { name: '\u200B', value: formatedPaymentDate || '-', inline: true },
          { name: '\u200B', value: formatedExpirationDate || '-', inline: true },
        );
      });

      await interaction.editReply({ embeds: [embedMessage] });
    } catch (error) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);

      await interaction.editReply({ content: 'Erro ao tentar consultar as colaborações' });
    }
  },
};

export default command;
