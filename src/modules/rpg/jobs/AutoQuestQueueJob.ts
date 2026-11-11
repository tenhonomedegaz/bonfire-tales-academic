import { container } from 'tsyringe';
import {
  ActionRowBuilder,
  ButtonBuilder,
  ButtonStyle,
  TextChannel,
} from 'discord.js';
import { subMinutes } from 'date-fns';

import { IBaseJob, BotClient } from '@/shared/providers/SchedulerProvider/models/IBaseJob';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { buildQuestQueueEmbed } from '@/modules/discord/commands/bonfire/rpg/quests/questQueue';
import { trustedNow } from '@/shared/util/dateTime';

interface JobData {
  guildId: string;
  questId: string;
}

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData: JobData;
}

export class AutoQuestQueueJob implements IBaseJob {
  public static jobName = 'quest-auto-queue';

  public async execute({ botClient, logger, jobData }: JobRequest): Promise<void> {
    try {
      const discordGuild = await botClient.guilds.fetch(jobData.guildId).catch(() => undefined);
      if (!discordGuild) return;

      const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
      const quest = await showQuestByIdUseCase.execute(jobData.questId);

      if (!quest) return;
      if (quest.status !== 'idle') return; // Se a missão já foi iniciada, pausada ou cancelada, não mandar fila
      if (!quest.channelId) return; // Precisa do canal criado

      const queuePostDate = subMinutes(quest.questDate, 20);
      const now = await trustedNow();
      const millisecondsUntilQueue = queuePostDate.getTime() - now.getTime();

      if (millisecondsUntilQueue > 1000) {
        logger.log(
          'info',
          `[${AutoQuestQueueJob.jobName}] Job fired early for quest ${quest.id}. ` +
            `Trusted now=${now.toISOString()} queueAt=${queuePostDate.toISOString()}. Waiting ${millisecondsUntilQueue}ms.`,
        );

        setTimeout(() => {
          this.execute({ botClient, logger, jobData }).catch((error) => {
            logger.log('error', `Error in delayed ${AutoQuestQueueJob.jobName}`, error);
          });
        }, Math.min(millisecondsUntilQueue, 2147483647));
        return;
      }

      const questChannel = await discordGuild.channels.fetch(quest.channelId).catch(() => null) as TextChannel;
      if (!questChannel || !questChannel.isTextBased()) return;

      const queueEmbed = await buildQuestQueueEmbed({ quest, guild: discordGuild });

      const queueControls = new ActionRowBuilder<ButtonBuilder>().addComponents(
        new ButtonBuilder()
          .setCustomId(`queue-confirm:${quest.id}`)
          .setLabel('Confirmar vaga')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId(`queue-leave:${quest.id}`)
          .setLabel('Desistir da vaga')
          .setStyle(ButtonStyle.Secondary),
      );

      const uniqueUserIds = new Set<string>();
      quest.mandatoryPlayers?.forEach((id) => uniqueUserIds.add(id));
      quest.highPriorityPlayers?.forEach((id) => uniqueUserIds.add(id));
      (quest.participationRequests ?? []).forEach((req) => uniqueUserIds.add(req.userId));

      const mentionsPing = Array.from(uniqueUserIds).map((id) => `<@${id}>`).join(' ');

      const sentMsg = await questChannel.send({
        content: `Fila da missão **${quest.name}**: ${mentionsPing}\n*(Postagem automática 20 minutos antes do início)*`,
        embeds: [queueEmbed],
        components: [queueControls],
      });

      if (mentionsPing.length > 0) {
        await sentMsg.edit({ content: `Fila da missão **${quest.name}**:\n*(Postagem automática 20 minutos antes do início)*` });
      }
    } catch (error) {
      logger.log('error', `Error in ${AutoQuestQueueJob.jobName}`, error);
    }
  }
}
