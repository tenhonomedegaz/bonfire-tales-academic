import { injectable, inject } from 'tsyringe';
import { addDays } from 'date-fns';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { AppError } from '@/shared/errors/AppError';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { DedicatedRank, RankReward } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { nowInBrazil } from '@/shared/util/dateTime';

import {
  computeDedicatedRankings,
  DEDICATED_RANK_PRIORITY_VALID_DAYS,
  DEDICATED_RANK_VALID_RANKS,
} from '@/modules/rpg/dedicatedRank/useCases/CalculateDedicatedRankUseCase';

type IRequest = {
  guildId: string;
  priorityRankName: string;
};

@injectable()
export class SetDedicatedRankPriorityUseCase implements IBaseUseCase {
  constructor(
    @inject('DedicatedRankRepository')
    private dedicatedRankRepository: IDedicatedRankRepository,
  ) {}

  public async execute({ guildId, priorityRankName }: IRequest): Promise<DedicatedRank> {
    if (!DEDICATED_RANK_VALID_RANKS.includes(priorityRankName)) {
      throw new AppError(
        `Rank inválido: "${priorityRankName}". Ranks válidos: ${DEDICATED_RANK_VALID_RANKS.join(', ')}`,
      );
    }

    const currentDedicatedRank = await this.dedicatedRankRepository.findCurrentByGuildId(guildId);
    const currentRankingsByName = new Map(
      currentDedicatedRank?.rankings.map((rank) => [rank.rankName, rank]) || [],
    );

    // Mantém as contagens de missões da semana atual e aplica a prioridade
    // em 0º lugar (recompensa máxima), sem empurrar os demais ranks para baixo.
    const rankOrderWithCounts = DEDICATED_RANK_VALID_RANKS.map((rankName) => ({
      rankName,
      questsCount: currentRankingsByName.get(rankName)?.questsCount || 0,
    }));

    const rankings: RankReward[] = computeDedicatedRankings(
      rankOrderWithCounts,
      priorityRankName,
    );

    const now = nowInBrazil();
    await this.dedicatedRankRepository.deactivateByGuildId(guildId);

    const dedicatedRank = new DedicatedRank({
      guildId,
      rankings,
      validFrom: now,
      validUntil: addDays(now, DEDICATED_RANK_PRIORITY_VALID_DAYS),
      isActive: true,
      isPriorityLocked: true,
      priorityRankName,
      createdAt: now,
      updatedAt: now,
    });

    return this.dedicatedRankRepository.create(dedicatedRank);
  }
}
