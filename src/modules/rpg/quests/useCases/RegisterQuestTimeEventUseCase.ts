// src/modules/rpg/quests/useCases/RegisterQuestTimeEventUseCase.ts

import { container } from 'tsyringe';
import { Guild } from 'discord.js';

import { AppError } from '@/shared/errors/AppError';
import { ShowQuestByIdUseCase } from './ShowQuestByIdUseCase';
import { UpdateQuestUseCase } from './UpdateQuestUseCase';
import { Quest, QuestPlayer, QuestTimeEvent } from '@/modules/rpg/quests/entities/Quest';
import { bonfireRoles } from '@/config/bonfire';
import { nowInBrazil } from '@/shared/util/dateTime';
import { questElapsedMinutes, questRewardAmount, recordParticipantRewards } from '@/modules/rpg/quests/services/questReward';


/**
 * Use Case Payload:
 * - discordGuild is optional. When provided, the use case manages the "Baixa Prioridade" role
 *   *only* when the quest starts ("run").
 * - On "finish" the role should NOT be removed — only an external 2-day timer should remove it.
 */
interface IRequest {
  questId: string;
  requesterUserId: string;
  eventType: 'run' | 'pause' | 'freeze' | 'finish';
  discordGuild?: Guild;
}

function consolidateQuestPlayers(quest: Quest): QuestPlayer[] {
  const playersByUserId = new Map<string, QuestPlayer>();

  quest.questPlayers?.forEach((player) => {
    if (player.userId) {
      playersByUserId.set(player.userId, player);
    }
  });

  quest.highPriorityPlayers?.forEach((userId) => {
    if (userId && !playersByUserId.has(userId)) {
      playersByUserId.set(userId, { userId, type: 'high-priority' });
    }
  });

  quest.mandatoryPlayers?.forEach((userId) => {
    if (userId && !playersByUserId.has(userId)) {
      playersByUserId.set(userId, { userId, type: 'high-priority' });
    }
  });

  quest.subscribedPlayers?.forEach((player: any) => {
    const userId = typeof player === 'string' ? player : player.userId;
    if (userId && !playersByUserId.has(userId)) {
      playersByUserId.set(userId, { userId, type: 'subscriber' });
    }
  });

  return [...playersByUserId.values()];
}

export class RegisterQuestTimeEventUseCase {
  public async execute({
    questId,
    requesterUserId,
    eventType,
    discordGuild,
  }: IRequest): Promise<Quest> {
    const showQuestByIdUseCase = container.resolve(ShowQuestByIdUseCase);
    const updateQuestUseCase = container.resolve(UpdateQuestUseCase);

    // Load quest
    const quest = await showQuestByIdUseCase.execute(questId);
    if (!quest) {
      throw new AppError('Quest not found');
    }

    // Validate event type
    const validEvents = ['run', 'pause', 'freeze', 'finish'];
    if (!validEvents.includes(eventType)) {
      throw new AppError(`Invalid event type: ${eventType}`);
    }

    // Register time event
    const timeEvent: QuestTimeEvent = {
      eventType,
      userId: requesterUserId,
      date: nowInBrazil(),
    };

    quest.timeEvents ??= [];
    quest.timeEvents.push(timeEvent);

    // Update quest status
    switch (eventType) {
      case 'run':
        if (quest.status === 'running') throw new AppError('A missão já está em andamento.');
        quest.status = 'running';
        break;
      case 'pause':
        if (quest.status === 'paused') throw new AppError('A missão já está pausada.');
        quest.status = 'paused';
        break;
      case 'freeze':
        if (quest.status === 'frozen') throw new AppError('A missão já está congelada.');
        quest.status = 'frozen';
        break;
      case 'finish':
        if (quest.status === 'finished') throw new AppError('A missão já foi finalizada.');
        quest.status = 'finished';
        quest.questPlayers = consolidateQuestPlayers(quest);
        const reward = questRewardAmount(questElapsedMinutes(quest), quest.rewardAventurasOverride);
        recordParticipantRewards(quest, reward, 'quest_finish', timeEvent.date.toISOString());
        quest.participationRequests = [];
        break;
    }

    // Persist changes
    return updateQuestUseCase.execute(quest);
  }
}

export default RegisterQuestTimeEventUseCase;
