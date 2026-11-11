/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { container } from 'tsyringe';
import ptBR, { format } from 'date-fns';
import { EmbedBuilder } from 'discord.js';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { CreateMemberUseCase } from '@/modules/members/useCases/CreateMemberUseCase';
import { ShowMemberByDiscordUserIdUseCase } from '@/modules/members/useCases/ShowMemberByDiscordUserIdUseCase';
import { UpdateMemberUseCase } from '@/modules/members/useCases/UpdateMemberUseCase';
import { bonfireRoles } from '@/config/bonfire';
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

export class GrantAdminModerationMonthlyTokensJob implements IBaseJob {
  public static jobName = 'admin-moderation-grant-monthly-tokens';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      let discordGuild = botClient.guilds.cache.find((guild) => guild.id === jobData.guildId);

      if (!discordGuild) {
        discordGuild = await botClient.guilds.fetch(jobData.guildId).catch(() => undefined);
      }

      if (!discordGuild) {
        logger.log('error', `Guild não encontrada para ${GrantAdminModerationMonthlyTokensJob.jobName}: ${jobData.guildId}`);
        return;
      }

      const testGuildIds = (process.env.TEST_GUILD_ID || '').split(',').map(id => id.trim()).filter(Boolean);
      if (testGuildIds.includes(jobData.guildId) && botClient.guilds.cache.size > testGuildIds.length) {
        logger.log('info', `[SCHEDULER] Skipping ${GrantAdminModerationMonthlyTokensJob.jobName} on Test Server ${jobData.guildId} to avoid global DB duplication.`);
        return;
      }

      await discordGuild.channels.fetch().catch(() => null);
      const logChannel = findBonfireLogChannel(discordGuild);

      if (!logChannel || !logChannel.isTextBased()) {
        logger.log('error', `Canal de log não encontrado para ${GrantAdminModerationMonthlyTokensJob.jobName}`);
        return;
      }

      const guildMembers = await discordGuild.members.fetch();
      const adminAndModerationMembers = guildMembers.filter(
        (member) =>
          !member.user.bot &&
          member.user.id !== '1167328059595182154' &&
          member.roles.cache.some(
            (role) =>
              role.name === bonfireRoles.adminRoleName ||
              role.name === bonfireRoles.moderatorRoleName,
          ),
      );

      const showMemberByDiscordUserIdUseCase = container.resolve(ShowMemberByDiscordUserIdUseCase);
      const createMemberUseCase = container.resolve(CreateMemberUseCase);
      const updateMemberUseCase = container.resolve(UpdateMemberUseCase);

      let grantedCount = 0;
      const grantedUsersIds: string[] = [];
      const errorLines: string[] = [];
      const jobStartDate = format(nowInBrazil(), 'yyyy-MM-dd HH:mm:ss', { locale: ptBR });

      for (const [, guildMember] of adminAndModerationMembers) {
        try {
          const existingMember = await showMemberByDiscordUserIdUseCase.execute({
            discordUserId: guildMember.user.id,
          });

          const member = existingMember || await createMemberUseCase.execute({
            discordUserId: guildMember.user.id,
            discordUserTag: guildMember.user.tag,
            email: `${guildMember.user.id}@discord.local`,
            tokenMission: 0,
            tokenXpBoost: 0,
            tokenSuperboost: 0,
            isModerator: false,
          });

          member.tokenMission += 1;
          member.tokenXpBoost += 1;

          await updateMemberUseCase.execute(member);
          grantedCount += 1;
          grantedUsersIds.push(guildMember.user.id);
        } catch (error) {
          logger.log(
            'error',
            `Erro ao conceder tokens mensais para ${guildMember.user.tag} - ${guildMember.user.id}`,
            error,
          );

          errorLines.push(`- <@${guildMember.user.id}>: ${error}`);
        }
      }

      const embedLines = [
        `**Iniciado em:** \`${jobStartDate}\``,
        '',
        '**Benefício:**',
        '+1 Missão Especial',
        '+1 Boost',
        '',
        '**Alvos:**',
        grantedUsersIds.length > 0 ? grantedUsersIds.map((userId) => `🟠 <@${userId}>`).join('\n') : 'Nenhum',
        '',
        `**Resumo:** ${grantedCount} membro(s) da administração/moderação receberam tokens.`,
      ];

      if (errorLines.length > 0) {
        embedLines.push('', '**Erros:**', errorLines.join('\n'));
      }

      const embed = new EmbedBuilder()
        .setColor('#f59e0b')
        .setTitle('🟠 Tokens Mensais de Administração/Moderação')
        .setDescription(embedLines.join('\n'))
        .setTimestamp();

      await logChannel.send({ embeds: [embed] });
    } catch (error) {
      logger.log('error', `Erro job (${GrantAdminModerationMonthlyTokensJob.jobName})`, error);
    }
  }
}
