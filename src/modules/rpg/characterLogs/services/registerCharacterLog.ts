import { prisma } from '@/shared/infra/database/prisma';
import { readCharacterLogSheet } from '@/modules/rpg/characterLogs/services/googleSheetsReader';

interface RegisterCharacterLogRequest {
  discordUserId: string;
  discordUserTag: string;
  sheetUrl: string;
  registeredBy: string;
  allowTransfer: boolean;
}

export async function registerCharacterLog({
  discordUserId,
  discordUserTag,
  sheetUrl,
  registeredBy,
  allowTransfer,
}: RegisterCharacterLogRequest) {
  const sheetData = await readCharacterLogSheet(sheetUrl);

  const existingLog = await prisma.characterLog.findFirst({
    where: { spreadsheetId: sheetData.spreadsheetId },
  });
  const existingCharacterLog = await prisma.characterLog.findFirst({
    where: {
      discordUserId,
      characterName: sheetData.characterName,
    },
  });
  const logToUpdate = existingLog ?? existingCharacterLog;

  if (logToUpdate && logToUpdate.discordUserId !== discordUserId && !allowTransfer) {
    throw new Error(`Esse log ja esta cadastrado para <@${logToUpdate.discordUserId}>. Somente o admin raiz pode transferir um log entre usuarios.`);
  }

  const userLogCountBeforeSave = await prisma.characterLog.count({
    where: {
      discordUserId,
      ...(logToUpdate ? { id: { not: logToUpdate.id } } : {}),
    },
  });
  const isOnlyUserLog = userLogCountBeforeSave === 0;
  const isNovice = isOnlyUserLog && sheetData.validStarterAdventures <= 2;

  const dataToSave = {
    discordUserId,
    discordUserTag,
    sheetUrl,
    spreadsheetId: sheetData.spreadsheetId,
    characterName: sheetData.characterName,
    rankName: sheetData.rankName,
    className: sheetData.className,
    level: sheetData.level,
    adventuresPlayed: sheetData.adventuresPlayed,
    validStarterAdventures: sheetData.validStarterAdventures,
    isNovice,
    registeredBy,
  };

  const savedLog = logToUpdate 
    ? await prisma.characterLog.update({ where: { id: logToUpdate.id }, data: dataToSave })
    : await prisma.characterLog.create({ data: dataToSave });

  if (!isOnlyUserLog) {
    await prisma.characterLog.updateMany({
      where: { discordUserId },
      data: { isNovice: false },
    });
  }

  return {
    savedLog,
    isNovice,
  };
}
