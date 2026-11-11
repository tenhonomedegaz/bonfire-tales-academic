import { injectable, inject } from 'tsyringe';
import { addDays } from 'date-fns';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { AppError } from '@/shared/errors/AppError';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { DedicatedRank, RankReward } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { nowInBrazil } from '@/shared/util/dateTime';

import {
  applyDedicatedRankPriority,
  DEDICATED_RANK_PRIORITY_VALID_DAYS,
  DEDICATED_RANK_REWARDS,
} from '@/modules/rpg/dedicatedRank/useCases/CalculateDedicatedRankUseCase';

type IRequest = {
  guildId: string;
  rankOrder: string[];
};

@injectable()
export class SetDedicatedRankManuallyUseCase implements IBaseUseCase {
  constructor(
    @inject('DedicatedRankRepository')
    private dedicatedRankRepository: IDedicatedRankRepository,
  ) {}

  public async execute({ guildId, rankOrder }: IRequest): Promise<DedicatedRank> {
    if (rankOrder.length < 2 || rankOrder.length > 5) {
      throw new AppError('Deve haver entre 2 e 5 ranks na ordem');
    }

    const currentDedicatedRank = await this.dedicatedRankRepository.findCurrentByGuildId(guildId);
    const priorityRankName = currentDedicatedRank?.isPriorityLocked
      ? currentDedicatedRank.priorityRankName
      : undefined;
    const sortedRankOrder = applyDedicatedRankPriority(
      rankOrder.map((rankName) => ({ rankName })),
      priorityRankName,
    ).map((rank) => rank.rankName);

    if (priorityRankName && !sortedRankOrder.includes(priorityRankName)) {
      sortedRankOrder.unshift(priorityRankName);
    }

    await this.dedicatedRankRepository.deactivateByGuildId(guildId);

    const rankings: RankReward[] = sortedRankOrder.map((rankName, index) => {
      // Com prioridade ativa, o rank prioritário ocupa o 0º lugar (índice 0) e os
      // demais seguem em 1º, 2º... Sem prioridade, a ordem manual vale a partir do 1º.
      let position: number;
      if (priorityRankName && rankName === priorityRankName) {
        position = 0;
      } else if (priorityRankName) {
        position = index;
      } else {
        position = index + 1;
      }

      const reward = DEDICATED_RANK_REWARDS[position as keyof typeof DEDICATED_RANK_REWARDS]
        || DEDICATED_RANK_REWARDS[4];

      return {
        rankName,
        position,
        questsCount: 0,
        rewardPerProgression: reward.perProgression,
        maxTotalReward: reward.maxTotal,
      };
    });

    const now = nowInBrazil();
    const validUntil = addDays(
      now,
      priorityRankName ? DEDICATED_RANK_PRIORITY_VALID_DAYS : 7,
    );

    const dedicatedRank = new DedicatedRank({
      guildId,
      rankings,
      validFrom: now,
      validUntil,
      isActive: true,
      isPriorityLocked: !!priorityRankName,
      priorityRankName,
      createdAt: now,
      updatedAt: now,
    });

    const created = await this.dedicatedRankRepository.create(dedicatedRank);
    return created;
  }
}
