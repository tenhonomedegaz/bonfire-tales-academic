import { prisma } from '@/shared/infra/database/prisma';

interface CleanupResult {
  removed: number;
}

function normalizeKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

async function removeDuplicatesByKey(keyBuilder: (log: any) => string): Promise<number> {
  const logs = await prisma.characterLog.findMany({
    orderBy: [{ updatedAt: 'desc' }, { createdAt: 'desc' }],
  });
  const seen = new Set<string>();
  const idsToRemove: string[] = [];

  logs.forEach((log) => {
    const key = keyBuilder(log);
    if (!key) {
      return;
    }

    if (seen.has(key)) {
      idsToRemove.push(String(log.id));
      return;
    }

    seen.add(key);
  });

  if (idsToRemove.length === 0) {
    return 0;
  }

  const result = await prisma.characterLog.deleteMany({ where: { id: { in: idsToRemove } } });
  return result.count ?? 0;
}

export async function cleanupDuplicateCharacterLogs(): Promise<CleanupResult> {
  const removedBySheet = await removeDuplicatesByKey((log) => log.spreadsheetId);
  const removedByCharacter = await removeDuplicatesByKey((log) =>
    `${log.discordUserId}:${normalizeKey(log.characterName)}`,
  );

  return {
    removed: removedBySheet + removedByCharacter,
  };
}
