import { container } from 'tsyringe';
import { v4 as uuidv4 } from 'uuid';
import { SlashCommandBuilder } from '@discordjs/builders';
import { EmbedBuilder } from 'discord.js';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles, bonfireSubscriptionOffers, thumbnails } from '@/config/bonfire';
import { CreateTransactionUseCase } from '@/modules/transactions/useCases/CreateTransactionUseCase';
import { Colors } from '@/config/discord';
import { nowInBrazil } from '@/shared/util/dateTime';


import {
  computeExpirationFromOfferId,
  findSubscriptionOfferById,
} from '@/modules/transactions/utils/subscriptionUtils';

const commandData = new SlashCommandBuilder()
  .setName('pagamento-adicionar')
  .setDescription('🔥 Adiciona um pagamento')
  .addStringOption((option) =>
    option.setName('email').setDescription('Email').setRequired(true),
  )
  .addStringOption((option) => {
    option.setName('plano').setDescription('Selecione o plano').setRequired(true);

    option.addChoices(
      ...bonfireSubscriptionOffers.map((offer) => ({
        name: `${offer.displayName} — R$ ${offer.price}`,
        value: offer.id,
      })),
    );

    return option;
  });

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.adminRoleName],
  cooldown: 3 * 1000,

  async execute(bot, interaction) {
    try {
      if (!interaction.deferred && !interaction.replied) {
        await interaction.deferReply({ ephemeral: true });
      }

      const email = interaction.options.getString('email', true);
      const subscriptionPlan = interaction.options.getString('plano', true);

      const offer = findSubscriptionOfferById(subscriptionPlan);

      if (!offer) {
        bot.logger?.log('warn', `pagamento-adicionar: unknown plan "${subscriptionPlan}"`);

        await interaction.editReply({
          content:
            `❌ **Plano desconhecido.** Use um plano da lista!\n\nPlanos disponíveis:\n` +
            bonfireSubscriptionOffers
              .map((o) => `• **${o.id}** — ${o.displayName} — R$ ${o.price}`)
              .join('\n'),
        });
        return;
      }

      const today = nowInBrazil();
      const expirationDate = computeExpirationFromOfferId(subscriptionPlan, today);

      // Normalize expiration date to midnight (prevents timezone expiration bugs)
      expirationDate.setHours(0, 0, 0, 0);

      const grossAmount = offer.price;

      const createTransactionUseCase = container.resolve(CreateTransactionUseCase);

      const newTransaction = await createTransactionUseCase.execute({
        transactionCode: uuidv4(),
        transactionSource: 'MANUAL',
        paymentDate: today,
        expirationDate,
        subscriptionPlan,
        subscriptionPeriod: offer.months + 'm',
        subscriptionReference: 'MANUAL',
        status: 1,
        grossAmount,
        netAmount: grossAmount,
        name: email,
        email,
        comments: 'Transação criada pelo comando /pagamento-adicionar',
        claimed: false,
        claimedAt: undefined,
      });

      const embedMessage = new EmbedBuilder()
        .setThumbnail(thumbnails.crown)
        .setColor(Colors.green500)
        .setTitle(`🎉 TRANSAÇÃO ADICIONADA`)
        .setDescription(
          [
            `\`${email}\` recebeu o plano:`,
            `**${offer.displayName}**`,
            ``,
            `💰 Valor: **R$ ${grossAmount.toFixed(2)}**`,
            `📅 Expira em: **${expirationDate.toLocaleDateString('pt-BR')}**`,
            ``,
            `🧾 ID da Transação: \`${newTransaction.id}\``,
          ].join('\n'),
        )
        .setTimestamp();

      await interaction.editReply({ embeds: [embedMessage] });
    } catch (error: any) {
      bot.logger.log('error', `Erro no comando ${commandData.name}`, error);

      await interaction.editReply({
        content: `Erro ao processar o comando:\n${String(error?.message || error)}`,
      });
    }
  },
};

export default command;