import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { IQuestsRepository } from '@/modules/rpg/quests/repositories/IQuestsRepository';
import { PrismaQuestMapper } from '@/modules/rpg/quests/repositories/prisma/mappers/PrismaQuestMapper';
import {
  ICreateQuestDTO,
  IFindAllUserQuestsDTO,
  IFindAllOthersQuestsDTO,
  IFindAllPublishedQuestsDTO,
  IFindAllSubscribedInIntervalDTO,
  IFindAllQuestsCreatedInIntervalDTO,
} from '@/modules/rpg/quests/dtos';
import { prisma } from '@/shared/infra/database/prisma';

export class PrismaQuestsRepository implements IQuestsRepository {
  public async create({
    guildId,
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
    questPlayers,
    createdBy,
    channelId,
    isPublished,
    status,
    dedicatedRankId,
  }: ICreateQuestDTO): Promise<Quest> {
    const quest = await prisma.quest.create({
      data: {
        guildId,
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
        questPlayers: (questPlayers ?? []) as any,
        createdBy,
        channelId,
        isPublished,
        status: status ?? 'idle',
        dedicatedRankId,
      },
    });

    return PrismaQuestMapper.toDomain(quest);
  }

  public async findById(id: string): Promise<Quest | null> {
    const quest = await prisma.quest.findUnique({
      where: { id },
    });

    return quest ? PrismaQuestMapper.toDomain(quest) : null;
  }

  public async findByChannelId(channelId: string): Promise<Quest | null> {
    const quest = await prisma.quest.findFirst({
      where: { channelId },
    });

    return quest ? PrismaQuestMapper.toDomain(quest) : null;
  }

  public async deleteById(id: string): Promise<void> {
    await prisma.quest.delete({
      where: { id },
    });
  }

  public async save(data: Quest): Promise<Quest> {
    const raw = PrismaQuestMapper.toPersistence(data);
    const { id, ...updateData } = raw;

    const quest = await prisma.quest.update({
      where: { id },
      data: updateData,
    });

    if (!quest) {
      throw new Error('Missão não localizada');
    }

    return PrismaQuestMapper.toDomain(quest);
  }

  public async findAllUserQuests({
    userId,
    searchTerm,
    questStatus,
    options,
  }: IFindAllUserQuestsDTO): Promise<Quest[]> {
    const quests = await prisma.quest.findMany({
      where: {
        questMaster: userId,
        isPublished: true,
        OR: [
          { name: { contains: searchTerm, mode: 'insensitive' } },
          { description: { contains: searchTerm, mode: 'insensitive' } },
        ],
        ...(questStatus?.length ? { status: { in: questStatus } } : {}),
      },
      take: options?.limit || undefined,
    });

    return quests.map((quest) => PrismaQuestMapper.toDomain(quest));
  }

  public async findAllOthersQuests({
    userId,
    searchTerm,
    questStatus,
    options,
  }: IFindAllOthersQuestsDTO): Promise<Quest[]> {
    const quests = await prisma.quest.findMany({
      where: {
        createdBy: { not: userId },
        OR: [
          { name: { contains: searchTerm, mode: 'insensitive' } },
          { description: { contains: searchTerm, mode: 'insensitive' } },
        ],
        ...(questStatus?.length ? { status: { in: questStatus } } : {}),
      },
      orderBy: questStatus?.includes('finished')
        ? { questDate: 'desc' }
        : { questDate: 'asc' },
      take: options?.limit || undefined,
    });

    return quests.map((quest) => PrismaQuestMapper.toDomain(quest));
  }

  public async findAllPublishedQuests({
    searchTerm,
    questStatus,
    questDateAfter,
    questDateBefore,
    options,
  }: IFindAllPublishedQuestsDTO): Promise<Quest[]> {
    const quests = await prisma.quest.findMany({
      where: {
        isPublished: true,
        OR: [
          { name: { contains: searchTerm, mode: 'insensitive' } },
          { description: { contains: searchTerm, mode: 'insensitive' } },
        ],
        ...(questStatus?.length ? { status: { in: questStatus } } : { status: { not: 'finished' } }),
        ...(questDateAfter || questDateBefore ? {
          questDate: {
            ...(questDateAfter ? { gte: questDateAfter } : {}),
            ...(questDateBefore ? { lte: questDateBefore } : {}),
          }
        } : {}),
      },
      orderBy: { questDate: 'desc' },
      take: options?.limit || undefined,
    });

    return quests.map((quest) => PrismaQuestMapper.toDomain(quest));
  }

  public async findAllSubscribedInInterval({
    userId,
    startDate,
    endDate,
  }: IFindAllSubscribedInIntervalDTO): Promise<Quest[]> {
    const quests = await prisma.quest.findMany({
      where: {
        questPlayers: {
          path: ['$'],
          array_contains: [{ userId }]
        },
        questDate: {
          gte: startDate,
          lte: endDate,
        },
      },
    });

    return quests.map((quest) => PrismaQuestMapper.toDomain(quest));
  }

  public async findAllQuestsCreatedInInterval({
    guildId,
    startDate,
    endDate,
  }: IFindAllQuestsCreatedInIntervalDTO): Promise<Quest[]> {
    const quests = await prisma.quest.findMany({
      where: {
        guildId,
        createdAt: {
          gte: startDate,
          lte: endDate,
        },
      },
    });

    return quests.map((quest) => PrismaQuestMapper.toDomain(quest));
  }
}
