import { container } from 'tsyringe';
import { ChannelType } from 'discord.js';
import { subDays, startOfDay, endOfDay, addDays } from 'date-fns';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { CalculateDedicatedRankUseCase, DEDICATED_RANK_VALID_RANKS } from '@/modules/rpg/dedicatedRank/useCases/CalculateDedicatedRankUseCase';
import { bonfireRoles, bonfireRpgRankRoles, rankWithEmoji } from '@/config/bonfire';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { nowInBrazil } from '@/shared/util/dateTime';


interface JobData {
  guildId: string;
}

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData: JobData;
}

export class PublishDedicatedRankJob implements IBaseJob {
  public static jobName = 'dedicated-rank-publish';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      const discordGuild = await botClient.guilds.fetch(jobData.guildId);

      if (!discordGuild) {
        logger.log('error', `Guild not found (${jobData.guildId})`);
        return;
      }

      // Carrega todos os canais da guild
      await discordGuild.channels.fetch();

      // Procura o canal do ranque dedicado
      const dedicatedRankChannel = discordGuild.channels.cache.find(
        (ch) =>
          ch.type === ChannelType.GuildText &&
          ch.name === '🔰┃ranque-dedicado',
      );

      if (!dedicatedRankChannel || !dedicatedRankChannel.isTextBased()) {
        logger.log('error', `Dedicated rank channel not found`);
        return;
      }

      // Conta quantas quests cada rank teve na semana passada
      const now = nowInBrazil();
      const sevenDaysAgo = subDays(now, 7);
      const weekStart = startOfDay(sevenDaysAgo);

      const questsRepository = container.resolve<IQuestsRepository>('QuestsRepository');
      const quests = await questsRepository.findAllQuestsCreatedInInterval({
        guildId: jobData.guildId,
        startDate: weekStart,
        endDate: now,
      });

      // Pega todos os cargos da guild
      const guildRoles = await discordGuild.roles.fetch();
      const rankRoleMap: Record<string, string> = {}; // roleId -> rankName

      // Cria um map de roleId -> rankName pra ficar fácil depois
      for (const rankRole of bonfireRpgRankRoles) {
        if (DEDICATED_RANK_VALID_RANKS.includes(rankRole.name)) {
          const role = guildRoles.find((r) => r.name === rankRole.name);
          if (role) {
            rankRoleMap[role.id] = rankRole.name;
          }
        }
      }

      // Conta quantas quests cada rank teve
      const rankQuestCount: Record<string, number> = {};
      DEDICATED_RANK_VALID_RANKS.forEach((rank) => {
        rankQuestCount[rank] = 0;
      });

      for (const quest of quests) {
        const questRankNames = new Set<string>();
        for (const roleId of quest.allowedRanks) {
          const rankName = rankRoleMap[roleId];
          if (rankName && DEDICATED_RANK_VALID_RANKS.includes(rankName)) {
            questRankNames.add(rankName);
          }
        }
        for (const rankName of questRankNames) {
          rankQuestCount[rankName] = (rankQuestCount[rankName] || 0) + 1;
        }
      }

      const rankOrderWithCounts = DEDICATED_RANK_VALID_RANKS.map((rankName) => ({
        rankName,
        questsCount: rankQuestCount[rankName] || 0,
      }))
      .sort((a, b) => a.questsCount - b.questsCount);

      // Criar ranque dedicado baseado nessa ordem e publicar no canal
      const calculateDedicatedRankUseCase = container.resolve(CalculateDedicatedRankUseCase);
      const newDedicatedRank = await calculateDedicatedRankUseCase.execute({
        guildId: jobData.guildId,
        rankOrderWithCounts,
        validFrom: now,
      });

      // Calcula a próxima segunda-feira às 23:59
      const nextMonday = addDays(new Date(now), 7);
      nextMonday.setHours(23, 59, 0, 0);

      const rankMessageLines: string[] = ['# Ranque Dedicado da Semana', ''];

      for (const rank of newDedicatedRank.rankings) {
        rankMessageLines.push(
          `${rankWithEmoji(rank.rankName)} – +${rank.rewardPerProgression} moedas por progressão (até o máximo de ${rank.maxTotalReward})`,
        );
      }

      rankMessageLines.push('');
      rankMessageLines.push(`## 🕒 Período de validade:`);
      rankMessageLines.push(
        `De hoje até segunda-feira, ${nextMonday.toLocaleDateString('pt-BR')}, às 23:59.`,
      );

      const masterMentions = discordGuild.roles.cache
        .filter((r) => r.name === bonfireRoles.masterRoleName || r.name === bonfireRoles.testMasterRoleName)
        .map((r) => `<@&${r.id}>`)
        .join(' ');

      const message = `${masterMentions}\n\n${rankMessageLines.join('\n')}`;

      await dedicatedRankChannel.send(message);
      logger.log('info', `Dedicated rank published: ${newDedicatedRank.id}`);
    } catch (error) {
      logger.log('error', 'Error in PublishDedicatedRankJob', error);
    }
  }
}
