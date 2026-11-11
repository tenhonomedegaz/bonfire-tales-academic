import { injectable, inject } from 'tsyringe';
import { Guild } from 'discord.js';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { bonfireChannels, bonfireRoles } from '@/config/bonfire';
import { ISchedulerJobsRepository } from '@/modules/scheduler/repositories/ISchedulerJobsRepository';
import { AppError } from '@/shared/errors/AppError';
import { questInfoEmbedMessage } from '@/modules/discord/commands/bonfire/rpg/quests/questEmbeds';
import { isBotRootAdmin } from '@/modules/discord/util';

type Request = {
  questId: string;
  requesterUserId: string;
  requesterRoles: string[];
  discordGuild: Guild;
};

@injectable()
export class DeleteQuestUseCase implements IBaseUseCase {
  constructor(
    @inject('QuestsRepository')
    private questsRepository: IQuestsRepository,

    @inject('SchedulerJobsRepository')
    private schedulerJobsRepository: ISchedulerJobsRepository,
  ) {}

  public async execute({
    requesterUserId,
    requesterRoles,
    questId,
    discordGuild,
  }: Request): Promise<void> {
    const quest = await this.questsRepository.findById(questId);

    if (!quest) {
      throw new AppError('Missão não localizada');
    }

    // se não for admin/mod ou root admin, verifica se é o criador da quest
    const isRequesterAdminOrMod =
      requesterRoles.includes(bonfireRoles.adminRoleName) ||
      requesterRoles.includes(bonfireRoles.moderatorRoleName) ||
      isBotRootAdmin(requesterUserId);

    if (!isRequesterAdminOrMod) {
      if (quest.createdBy !== requesterUserId) {
        throw new AppError('Você não tem permissão para deletar essa missão');
      }
    }

    await this.questsRepository.deleteById(questId);

    const existingPublishJob = await this.schedulerJobsRepository.findQuestPublishJob({
      jobName: 'publish-quest',
      guildId: quest.guildId,
      questId: quest.id,
    });

    if (existingPublishJob) {
      await this.schedulerJobsRepository.deleteById(existingPublishJob.id);
    }

    if (quest.channelId) {
      try {
        const channels = await discordGuild.channels.fetch();
        const questChannel = channels.find((channel) => channel.id === quest.channelId);

        if (questChannel) {
          await questChannel.delete().catch((err) => {
            console.error(`Erro ao deletar canal da missão ${quest.id}:`, err);
          });
        }
      } catch (error) {
        console.error(`Erro ao buscar/deletar canal da missão ${quest.id}:`, error);
      }
    }

    if (quest.subscribedPlayers.length > 0) {
      const queuePlayersIds = quest.subscribedPlayers.map((queuePlayer) => queuePlayer.userId);
      const membersToNotify = discordGuild.members.cache.filter((member) =>
        queuePlayersIds.includes(member.id),
      );

      const cancelQuestInfoMessage = await questInfoEmbedMessage({ quest });

      const notifyPlayersPromisses = membersToNotify.map(async (member) => {
        await member.send({
          content: `<@${requesterUserId}> cancelou a missão:`,
          embeds: [cancelQuestInfoMessage],
        });
      });

      try {
        await Promise.allSettled(notifyPlayersPromisses);
      } catch (error) {
        console.log(error);
      }
    }

    const logChannel = discordGuild.channels.cache.find(
      (channel) => channel.name === bonfireChannels.logChannelName,
    );

    if (logChannel && logChannel.isTextBased()) {
      const questInfoMessage = await questInfoEmbedMessage({ quest, showQueueList: true });

      try {
        await logChannel.send({
          content: `<@${requesterUserId}> cancelou a missão:`,
          embeds: [questInfoMessage],
        });
      } catch (error) {
        console.log(error);
      }
    }
  }
}
