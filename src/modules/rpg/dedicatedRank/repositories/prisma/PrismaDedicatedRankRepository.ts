import { DedicatedRank } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { PrismaDedicatedRankMapper } from '@/modules/rpg/dedicatedRank/repositories/prisma/mappers/PrismaDedicatedRankMapper';
import { prisma } from '@/shared/infra/database/prisma';
import { nowInBrazil } from '@/shared/util/dateTime';

export class PrismaDedicatedRankRepository implements IDedicatedRankRepository {
  public async create(dedicatedRank: DedicatedRank): Promise<DedicatedRank> {
    const raw = PrismaDedicatedRankMapper.toPersistence(dedicatedRank);
    const { id, ...data } = raw;
    const created = await prisma.dedicatedRank.create({
      data: { ...data, id },
    });
    return PrismaDedicatedRankMapper.toDomain(created);
  }

  public async update(dedicatedRank: DedicatedRank): Promise<DedicatedRank> {
    const raw = PrismaDedicatedRankMapper.toPersistence(dedicatedRank);
    const { id, ...updateData } = raw;

    const updated = await prisma.dedicatedRank.update({
      where: { id },
      data: updateData,
    });

    return PrismaDedicatedRankMapper.toDomain(updated);
  }

  public async findCurrentByGuildId(guildId: string): Promise<DedicatedRank | null> {
    const now = nowInBrazil();
    const dedicatedRank = await prisma.dedicatedRank.findFirst({
      where: {
        guildId,
        isActive: true,
        validFrom: { lte: now },
        validUntil: { gte: now },
      },
      orderBy: { createdAt: 'desc' },
    });

    return dedicatedRank ? PrismaDedicatedRankMapper.toDomain(dedicatedRank) : null;
  }

  public async deactivateByGuildId(guildId: string): Promise<void> {
    await prisma.dedicatedRank.updateMany({
      where: { guildId, isActive: true },
      data: { isActive: false },
    });
  }

  public async findById(id: string): Promise<DedicatedRank | null> {
    const dedicatedRank = await prisma.dedicatedRank.findUnique({
      where: { id },
    });
    return dedicatedRank ? PrismaDedicatedRankMapper.toDomain(dedicatedRank) : null;
  }
}
