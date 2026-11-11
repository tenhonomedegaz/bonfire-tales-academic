import 'reflect-metadata';
import { container } from 'tsyringe';

import { Quest } from '@/modules/rpg/quests/entities/Quest';
import { questRewardAmount, recordParticipantRewards } from '@/modules/rpg/quests/services/questReward';
import { RegisterQuestTimeEventUseCase } from '@/modules/rpg/quests/useCases/RegisterQuestTimeEventUseCase';
import { PrismaQuestMapper } from '@/modules/rpg/quests/repositories/prisma/mappers/PrismaQuestMapper';
import { ShowQuestByIdUseCase } from '@/modules/rpg/quests/useCases/ShowQuestByIdUseCase';
import { UpdateQuestUseCase } from '@/modules/rpg/quests/useCases/UpdateQuestUseCase';

describe('finalized quest participant reward contract', () => {
  afterEach(() => jest.restoreAllMocks());

  it('stores each active participant amount, source and time without changing a partial removal', async () => {
    const quest = {
      id: 'quest-1', status: 'running', rewardAventurasOverride: undefined,
      questPlayers: [
        { userId: 'active', type: 'normal' },
        { userId: 'removed', type: 'normal', removedAt: new Date(),
          removedWithReward: true, rewardAmount: 2 },
      ],
      timeEvents: [{ eventType: 'run', userId: 'gm', date: new Date(Date.now() - 151 * 60000) }],
      highPriorityPlayers: [], mandatoryPlayers: [], subscribedPlayers: [],
      participationRequests: [{ userId: 'candidate' }],
    } as unknown as Quest;
    const save = jest.fn(async (value: Quest) => value);
    jest.spyOn(container, 'resolve').mockImplementation((target: any) => {
      if (target === ShowQuestByIdUseCase) return { execute: async () => quest } as any;
      if (target === UpdateQuestUseCase) return { execute: save } as any;
      throw new Error('unexpected dependency');
    });

    const result = await new RegisterQuestTimeEventUseCase().execute({
      questId: quest.id, requesterUserId: 'gm', eventType: 'finish',
    });

    expect(save).toHaveBeenCalledTimes(1);
    expect(result.questPlayers.find((p) => p.userId === 'active')).toMatchObject({
      rewardAmount: 1, rewardSource: 'quest_finish',
    });
    expect(result.questPlayers.find((p) => p.userId === 'active')?.rewardFinalizedAt).toBeTruthy();
    expect(PrismaQuestMapper.toPersistence(result).questPlayers[0]).toMatchObject({
      rewardAmount: 1, rewardSource: 'quest_finish',
    });
    expect(result.questPlayers.find((p) => p.userId === 'removed')?.rewardAmount).toBe(2);
    expect(result.questPlayers.find((p) => p.userId === 'removed')?.rewardFinalizedAt).toBeUndefined();
    expect(result.participationRequests).toEqual([]);
  });

  it('uses the existing threshold and explicit override for the persisted credit', () => {
    expect(questRewardAmount(149)).toBe(0);
    expect(questRewardAmount(150)).toBe(1);
    expect(questRewardAmount(300)).toBe(2);
    expect(questRewardAmount(300, 4)).toBe(4);
  });

  it('updates active participant credits after a staff override, preserving partial removal', () => {
    const quest = { questPlayers: [
      { userId: 'active', type: 'normal', rewardAmount: 1 },
      { userId: 'removed', type: 'normal', removedAt: new Date(),
        removedWithReward: true, rewardAmount: 2 },
    ] } as unknown as Quest;
    recordParticipantRewards(quest, 4, 'staff_override', '2026-09-28T13:00:00Z');
    expect(quest.questPlayers[0]).toMatchObject({
      rewardAmount: 4, rewardSource: 'staff_override',
      rewardFinalizedAt: '2026-09-28T13:00:00Z',
    });
    expect(quest.questPlayers[1].rewardAmount).toBe(2);
    expect(quest.questPlayers[1].rewardFinalizedAt).toBeUndefined();
  });
});
