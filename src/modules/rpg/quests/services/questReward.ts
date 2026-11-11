import { differenceInSeconds } from 'date-fns';

import { Quest } from '@/modules/rpg/quests/entities/Quest';

export function questElapsedMinutes(quest: Quest): number {
  const events = quest.timeEvents ?? [];
  let seconds = 0;
  for (let i = 0; i < events.length - 1; i += 1) {
    if (events[i].eventType === 'run') {
      seconds += Math.max(0, differenceInSeconds(events[i + 1].date, events[i].date));
    }
  }
  return Math.floor(seconds / 60);
}

export function questRewardAmount(minutes: number, override?: number | null): number {
  if (override !== undefined && override !== null) return Math.max(0, override);
  let amount = 0;
  if (minutes >= 150) amount = 1;
  if (minutes >= 300) amount = 2;
  if (minutes >= 450) amount = 3;
  if (minutes >= 600) amount = 4;
  if (minutes >= 900) amount = 6;
  if (minutes >= 1200) amount = 8;
  const extra = minutes > 1200 ? Math.floor((minutes - 1200) / 600) : 0;
  return amount + extra * 4;
}

export function recordParticipantRewards(
  quest: Quest,
  amount: number,
  source: 'quest_finish' | 'staff_override',
  finalizedAt: string,
): void {
  quest.questPlayers = (quest.questPlayers ?? []).map((player) => player.removedAt ? player : {
    ...player,
    rewardAmount: amount,
    rewardFinalizedAt: finalizedAt,
    rewardSource: source,
  });
}
