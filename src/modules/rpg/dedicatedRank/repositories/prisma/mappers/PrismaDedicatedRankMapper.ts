import { DedicatedRank } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { DedicatedRank as PrismaDedicatedRank } from '@prisma/client';

export class PrismaDedicatedRankMapper {
  static toDomain(rank: PrismaDedicatedRank): DedicatedRank {
    return {
      id: rank.id,
      guildId: rank.guildId,
      rankings: rank.rankings as any,
      validFrom: rank.validFrom,
      validUntil: rank.validUntil,
      isActive: rank.isActive,
      isPriorityLocked: rank.isPriorityLocked,
      priorityRankName: rank.priorityRankName ?? undefined,
      createdAt: rank.createdAt,
      updatedAt: rank.updatedAt,
    };
  }

  static toPersistence(rank: DedicatedRank): any {
    return {
      id: rank.id,
      guildId: rank.guildId,
      rankings: rank.rankings,
      validFrom: rank.validFrom,
      validUntil: rank.validUntil,
      isActive: rank.isActive,
      isPriorityLocked: rank.isPriorityLocked,
      priorityRankName: rank.priorityRankName,
      createdAt: rank.createdAt,
      updatedAt: rank.updatedAt,
    };
  }
}
