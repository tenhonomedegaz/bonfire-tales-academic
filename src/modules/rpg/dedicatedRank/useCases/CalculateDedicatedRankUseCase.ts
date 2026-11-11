import { injectable, inject } from 'tsyringe';
import { addDays } from 'date-fns';
import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IDedicatedRankRepository } from '@/modules/rpg/dedicatedRank/repositories/IDedicatedRankRepository';
import { DedicatedRank, RankReward } from '@/modules/rpg/dedicatedRank/entities/DedicatedRank';
import { nowInBrazil } from '@/shared/util/dateTime';


export const DEDICATED_RANK_VALID_RANKS = [
  'Obsidiana (1-4)',
  'Ametista (5-8)',
  'Topázio (9-12)',
  'Esmeralda (13-16)',
  'Âmbar (17-19)',
];

export const DEDICATED_RANK_REWARDS = {
  // 0º lugar: rank prioritário, fora da disputa — sempre recompensa máxima
  0: { perProgression: 50, maxTotal: 150 },
  1: { perProgression: 50, maxTotal: 150 },
  2: { perProgression: 40, maxTotal: 120 },
  3: { perProgression: 30, maxTotal: 90 },
  4: { perProgression: 20, maxTotal: 60 },
};

export const DEDICATED_RANK_PRIORITY_VALID_DAYS = 3650;

export function applyDedicatedRankPriority<T extends { rankName: string }>(
  rankOrder: T[],
  priorityRankName?: string,
): T[] {
  if (!priorityRankName) {
    return rankOrder;
  }

  const priorityRank = rankOrder.find((rank) => rank.rankName === priorityRankName);
  if (!priorityRank) {
    return rankOrder;
  }

  return [
    priorityRank,
    ...rankOrder.filter((rank) => rank.rankName !== priorityRankName),
  ];
}

/**
 * Calcula as posições e recompensas do ranque dedicado a partir da contagem de
 * missões por rank.
 *
 * Regras:
 * - O rank prioritário (se houver) fica em 0º lugar: fora da disputa e sempre
 *   com a recompensa máxima.
 * - Os demais ranks são ranqueados entre si por quantidade de missões (menos
 *   missões = melhor recompensa), começando do 1º lugar. Ou seja, a prioridade
 *   NÃO empurra mais os outros para baixo — o rank não prioritário com menos
 *   missões também ganha a recompensa máxima.
 * - Qualquer rank sem missões na semana (questsCount === 0) fica em 1º lugar.
 */
export function computeDedicatedRankings(
  rankOrderWithCounts: Array<{ rankName: string; questsCount: number }>,
  priorityRankName?: string,
): RankReward[] {
  const byCountAsc = [...rankOrderWithCounts].sort(
    (a, b) => a.questsCount - b.questsCount,
  );
  const sortedRankOrder = applyDedicatedRankPriority(byCountAsc, priorityRankName);

  const rankingsWithoutPriority = priorityRankName
    ? sortedRankOrder.filter((rank) => rank.rankName !== priorityRankName)
    : sortedRankOrder;

  return sortedRankOrder.map((item) => {
    let position: number;

    if (priorityRankName && item.rankName === priorityRankName) {
      position = 0;
    } else if (item.questsCount === 0) {
      position = 1;
    } else {
      const tieIndex = rankingsWithoutPriority.findIndex(
        (el) => el.questsCount === item.questsCount,
      );
      position = tieIndex + 1;
    }

    const reward = DEDICATED_RANK_REWARDS[position as keyof typeof DEDICATED_RANK_REWARDS]
      || DEDICATED_RANK_REWARDS[4];

    return {
      rankName: item.rankName,
      position,
      questsCount: item.questsCount,
      rewardPerProgression: reward.perProgression,
      maxTotalReward: reward.maxTotal,
    };
  });
}

type IRequest = {
  guildId: string;
  rankOrderWithCounts: Array<{ rankName: string; questsCount: number }>;
  validFrom: Date;
};

@injectable()
export class CalculateDedicatedRankUseCase implements IBaseUseCase {
  constructor(
    @inject('DedicatedRankRepository')
    private dedicatedRankRepository: IDedicatedRankRepository,
  ) {}

  public async execute({
    guildId,
    rankOrderWithCounts,
    validFrom,
  }: IRequest): Promise<DedicatedRank> {
    const currentDedicatedRank = await this.dedicatedRankRepository.findCurrentByGuildId(guildId);
    const priorityRankName = currentDedicatedRank?.isPriorityLocked
      ? currentDedicatedRank.priorityRankName
      : undefined;

    await this.dedicatedRankRepository.deactivateByGuildId(guildId);

    const rankings = computeDedicatedRankings(rankOrderWithCounts, priorityRankName);

    const validUntil = addDays(
      validFrom,
      priorityRankName ? DEDICATED_RANK_PRIORITY_VALID_DAYS : 7,
    );

    const dedicatedRank = new DedicatedRank({
      guildId,
      rankings,
      validFrom,
      validUntil,
      isActive: true,
      isPriorityLocked: !!priorityRankName,
      priorityRankName,
      createdAt: nowInBrazil(),
      updatedAt: nowInBrazil(),
    });

    const created = await this.dedicatedRankRepository.create(dedicatedRank);
    return created;
  }
}
