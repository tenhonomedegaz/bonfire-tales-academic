import { prisma } from '@/shared/infra/database/prisma';

export async function getLastPlayedDates(userIds: string[]): Promise<Map<string, Date | null>> {
  const quests = await prisma.quest.findMany({
    where: {
      status: { in: ['running', 'paused', 'frozen', 'finished'] },
    },
    select: {
      startDate: true,
      questDate: true,
      questPlayers: true,
    },
  });

  const lastPlayedMap = new Map<string, Date | null>();
  userIds.forEach(id => lastPlayedMap.set(id, null));

  for (const quest of quests) {
    if (!quest.questPlayers || !Array.isArray(quest.questPlayers)) continue;
    const players = quest.questPlayers as any[];

    for (const player of players) {
      const uId = player.userId;
      if (!userIds.includes(uId)) continue;

      const date = quest.startDate || quest.questDate;
      if (date) {
        const currentLastPlayed = lastPlayedMap.get(uId);
        if (!currentLastPlayed || date.getTime() > currentLastPlayed.getTime()) {
          lastPlayedMap.set(uId, date);
        }
      }
    }
  }

  return lastPlayedMap;
}
