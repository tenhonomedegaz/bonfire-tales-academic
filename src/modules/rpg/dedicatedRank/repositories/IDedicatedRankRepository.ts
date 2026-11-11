import { DedicatedRank } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';

export interface IDedicatedRankRepository {
  create(dedicatedRank: DedicatedRank): Promise<DedicatedRank>;
  update(dedicatedRank: DedicatedRank): Promise<DedicatedRank>;
  findCurrentByGuildId(guildId: string): Promise<DedicatedRank | null>;
  findById(id: string): Promise<DedicatedRank | null>;
  deactivateByGuildId(guildId: string): Promise<void>;
}
