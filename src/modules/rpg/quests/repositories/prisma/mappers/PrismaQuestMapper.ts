import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { Quest as PrismaQuest } from '@prisma/client';

export class PrismaQuestMapper {
  static toDomain(quest: PrismaQuest): Quest {
    const {
      id,
      guildId,
      channelId,
      name,
      description,
      questDate,
      playersAmount,
      rules,
      tags,
      type,
      tableUrl,
      questMaster,
      allowedRanks,
      mandatoryPlayers,
      highPriorityPlayers,
      subscribedPlayers,
      questPlayers,
      participationRequests,
      removedPlayers,
      createdBy,
      isPublished,
      status,
      timeEvents,
      startDate,
      endDate,
      rewardAventurasOverride,
      dedicatedRankId,
      createdAt,
      updatedAt,
    } = quest;

    return {
      id,
      guildId,
      channelId,
      name,
      description,
      questDate,
      playersAmount,
      rules,
      tags,
      type,
      tableUrl,
      questMaster,
      allowedRanks,
      mandatoryPlayers: mandatoryPlayers ?? [],
      highPriorityPlayers,
      subscribedPlayers: (subscribedPlayers as any) ?? [],
      questPlayers: Array.isArray(questPlayers)
        ? (questPlayers as any).map((p: any) => ({
            ...p,
            removedAt: p.removedAt ? new Date(p.removedAt) : undefined,
          }))
        : [],
      participationRequests: Array.isArray(participationRequests)
        ? (participationRequests as any).map((req: any) => ({
            ...req,
            requestDate: new Date(req.requestDate),
            confirmedAt: req.confirmedAt ? new Date(req.confirmedAt) : undefined,
          }))
        : [],
      removedPlayers: removedPlayers ?? [],
      createdBy,
      isPublished,
      status: status as any,
      timeEvents: Array.isArray(timeEvents)
        ? (timeEvents as any).map((ev: any) => ({
            ...ev,
            date: new Date(ev.date),
          }))
        : [],
      startDate,
      endDate,
      rewardAventurasOverride,
      dedicatedRankId,
      createdAt,
      updatedAt,
    };
  }

  static toPersistence(quest: Quest): any {
    return {
      id: quest.id,
      guildId: quest.guildId,
      channelId: quest.channelId,
      name: quest.name,
      description: quest.description,
      questDate: quest.questDate,
      playersAmount: quest.playersAmount,
      rules: quest.rules,
      tags: quest.tags,
      type: quest.type,
      tableUrl: quest.tableUrl,
      questMaster: quest.questMaster,
      allowedRanks: quest.allowedRanks,
      mandatoryPlayers: quest.mandatoryPlayers ?? [],
      highPriorityPlayers: quest.highPriorityPlayers,
      subscribedPlayers: quest.subscribedPlayers ?? [],
      questPlayers: quest.questPlayers ?? [],
      participationRequests: quest.participationRequests ?? [],
      removedPlayers: quest.removedPlayers ?? [],
      createdBy: quest.createdBy,
      isPublished: quest.isPublished,
      status: quest.status,
      timeEvents: quest.timeEvents ?? [],
      startDate: quest.startDate,
      endDate: quest.endDate,
      rewardAventurasOverride: quest.rewardAventurasOverride,
      dedicatedRankId: quest.dedicatedRankId,
      createdAt: quest.createdAt,
      updatedAt: quest.updatedAt,
    };
  }
}
