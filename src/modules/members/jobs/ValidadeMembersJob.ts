/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';
import ptBR, { format } from 'date-fns';
import { EmbedBuilder } from 'discord.js';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { ShowMembersWithActiveSubscriptionUseCase } from '@/modules/members/useCases/ShowMembersWithActiveSubscriptionUseCase';
import { ClaimTransactionsTokensUseCase } from '@/modules/transactions/useCases/ClaimTransactionsTokensUseCase';
import { bonfireChannels, bonfireRoles } from '@/config/bonfire';
import { createSubscriptionInfoEmbedMessages } from '@/modules/discord/commands/bonfire/subscription/subscriptionEmbeds';
import { findBonfireLogChannel } from '@/modules/discord/util';
import { nowInBrazil } from '@/shared/util/dateTime';


interface JobData {
  guildId: string;
}

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData: JobData;
}

export class ValidadeMembersJob implements IBaseJob {
  public static jobName = 'members-validate-subscription';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      const discordGuild = botClient.guilds.cache.find((guild) => guild.id === jobData.guildId);

      if (!discordGuild) {
        logger.log(
          'error',
          `Não foi possível localizar o servidor \`${jobData.guildId}\` no Discord para continuar com o processo de validação de assinaturas agendado`,
        );
        return;
      }

      await discordGuild.channels.fetch().catch(() => null);
      const logChannel = findBonfireLogChannel(discordGuild);

      if (!logChannel || !logChannel.isTextBased()) {
        logger.log(
          'error',
          `Não foi possível localizar o canal \`${bonfireChannels.logChannelName}\` no Discord para continuar com o processo de validação de assinaturas agendado`,
        );
        return;
      }

      const subscriberRole = discordGuild.roles.cache.find(
        (role) => role.name === bonfireRoles.subscriberRoleName,
      );
      const moderatorRole = discordGuild.roles.cache.find(
        (role) => role.name === bonfireRoles.moderatorRoleName,
      );
      const adminRole = discordGuild.roles.cache.find(
        (role) => role.name === bonfireRoles.adminRoleName,
      );

      if (!subscriberRole) {
        logger.log(
          'error',
          `Não foi possível localizar o cargo (${bonfireRoles.subscriberRoleName}) no servidor (${jobData.guildId}) para continuar com o processo de validação de assinaturas agendado`,
        );

        await logChannel.send(`Erro: não foi possível localizar o cargo (${bonfireRoles.subscriberRoleName}) no servidor \`${jobData.guildId}\``);
        return;
      }

      const jobStartDate = format(nowInBrazil(), 'yyyy-MM-dd HH:mm:ss', {
        locale: ptBR,
      });
      const guaranteedStaffUsers: { userId: string; benefitSource: string }[] = [];
      const activatedSubscriberUsersIds: string[] = [];
      const expiredRemovedUsersIds: string[] = [];
      const errorLines: string[] = [];

      const guildMembers = await discordGuild.members.fetch();

      const lifetimeSubscriberMembers = guildMembers.filter(
        (member) =>
          !member.user.bot &&
          (
            (!!moderatorRole && member.roles.cache.has(moderatorRole.id)) ||
            (!!adminRole && member.roles.cache.has(adminRole.id))
          ),
      );

      for (const [, member] of lifetimeSubscriberMembers) {
        if (!member.roles.cache.has(subscriberRole.id)) {
          try {
            const benefitSource = member.roles.cache.has(adminRole?.id || '')
              ? bonfireRoles.adminRoleName
              : bonfireRoles.moderatorRoleName;

            await member.roles.add(subscriberRole);
            guaranteedStaffUsers.push({ userId: member.user.id, benefitSource });
          } catch (error) {
            logger.log(
              'error',
              `Erro ao tentar adicionar o cargo (${subscriberRole.name}) por administração/moderação ${member.user.tag} - ${member.user.id}`,
              error,
            );

            errorLines.push(`- Erro ao garantir \`${subscriberRole.name}\` para <@${member.user.id}>: ${error}`);
          }
        }
      }

      const showMembersWithActiveSubscriptionUseCase = container.resolve(
        ShowMembersWithActiveSubscriptionUseCase,
      );
      const activeSubscribers = await showMembersWithActiveSubscriptionUseCase.execute();

      const activeSubscribersDiscordUserIds = activeSubscribers.map(
        (discordSubscriber) => discordSubscriber.discordUserId,
      );

      const claimTransactionsTokens = container.resolve(ClaimTransactionsTokensUseCase);
      for (const subscriber of activeSubscribers) {
        try {
          await claimTransactionsTokens.execute(subscriber);
          const guildMember = guildMembers.get(subscriber.discordUserId);
          if (guildMember && !guildMember.roles.cache.has(subscriberRole.id)) {
            await guildMember.roles.add(subscriberRole);
            activatedSubscriberUsersIds.push(subscriber.discordUserId);
          }
        } catch (error) {
          logger.log(
            'error',
            `Erro ao aplicar beneficios automaticos para ${subscriber.discordUserTag} - ${subscriber.discordUserId}`,
            error,
          );
          errorLines.push(`- Erro ao ativar beneficios para <@${subscriber.discordUserId}>: ${error}`);
        }
      }

      const expiredDiscordUsers = guildMembers.filter(
        (member) =>
          !member.user.bot &&
          !activeSubscribersDiscordUserIds.includes(member.user.id) &&
          !member.roles.cache.some((role) => role.name === bonfireRoles.moderatorRoleName) &&
          !member.roles.cache.some((role) => role.name === bonfireRoles.adminRoleName) &&
          member.roles.cache.some((role) => role.name === bonfireRoles.subscriberRoleName),
      );

      const batchSize = 10;
      let countBatchSize = 0;
      for (const [, member] of expiredDiscordUsers) {
        try {
          countBatchSize += 1;

          await member.roles.remove(subscriberRole);
          expiredRemovedUsersIds.push(member.user.id);

          const subscriptionEmbeds = createSubscriptionInfoEmbedMessages({
            discordUserId: member.user.id,
            discordUsername: member.user.tag,
          });

          const message = [
            'Olá aventureiro!',
            'Seu período de colaborador terminou. Caso queira continuar colaborando com o crescimento do servidor e mantendo seus benefícios, renove sua assinatura.',
            '',
            'Lembramos que o uso do servidor é totalmente gratuito e o dinheiro investido é para a manutenção do próprio. Agradecemos imensamente o apoio.',
          ];

          await member.send({
            content: message.join('\n'),
            embeds: subscriptionEmbeds,
          });

          if (countBatchSize === batchSize) {
            countBatchSize = 1;
            await new Promise((resolve) => {
              setTimeout(resolve, 3000);
            });
          }
        } catch (error) {
          logger.log(
            'error',
            `Erro ao tentar remover o cargo (${subscriberRole.name}) do usuário ${member.user.tag} - ${member.user.id}`,
            error,
          );

          errorLines.push(`- Erro ao remover \`${subscriberRole.name}\` de <@${member.user.id}>: ${error}`);
        }
      }

      const jobFinishDate = format(nowInBrazil(), 'yyyy-MM-dd HH:mm:ss', {
        locale: ptBR,
      });

      const embedLines = [
        `**Iniciado em:** \`${jobStartDate}\``,
        `**Finalizado em:** \`${jobFinishDate}\``,
        '',
        '**Colaborador garantido por administração/moderação:**',
        guaranteedStaffUsers.length > 0
          ? guaranteedStaffUsers.map((entry) => `🟣 <@${entry.userId}> - \`${entry.benefitSource}\``).join('\n')
          : 'Nenhum novo cargo garantido',
        '',
        '**Colaborador ativado por pagamento:**',
        activatedSubscriberUsersIds.length > 0
          ? activatedSubscriberUsersIds.map((userId) => `🟢 <@${userId}>`).join('\n')
          : 'Nenhum novo pagamento para ativar',
        '',
        '**Colaborador removido por assinatura expirada:**',
        expiredRemovedUsersIds.length > 0
          ? expiredRemovedUsersIds.map((userId) => `🟣 <@${userId}>`).join('\n')
          : `Nenhum membro expirado possuía \`${bonfireRoles.subscriberRoleName}\``,
      ];

      if (errorLines.length > 0) {
        embedLines.push('', '**Erros:**', errorLines.join('\n'));
      }

      const embed = new EmbedBuilder()
        .setColor('#8b5cf6')
        .setTitle('🟣 Validação de Colaboradores')
        .setDescription(embedLines.join('\n'))
        .setTimestamp();

      if (
        guaranteedStaffUsers.length > 0 ||
        activatedSubscriberUsersIds.length > 0 ||
        expiredRemovedUsersIds.length > 0 ||
        errorLines.length > 0
      ) {
        await logChannel.send({ embeds: [embed] });
      }
    } catch (error) {
      logger.log('error', 'Erro job (ValidadeMembersJob)', error);
    }
  }
}
