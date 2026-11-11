import { google } from 'googleapis';

export interface CharacterLogSheetData {
  spreadsheetId: string;
  characterName: string;
  rankName: string;
  className: string;
  level: number | null;
  adventuresPlayed: number;
  validStarterAdventures: number;
}

const ignoredStarterMissionTerms = ['booster', 'salario', 'salário', 'token', 'boost', 'nitro'];

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

function hasIgnoredStarterTerm(missionName: string): boolean {
  if (!missionName) return false;
  const normalizedMissionName = normalizeText(missionName);
  return ignoredStarterMissionTerms.some((term) => normalizedMissionName.includes(normalizeText(term)));
}

function extractSpreadsheetId(sheetUrlOrId: string): string {
  const match = sheetUrlOrId.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);

  if (match?.[1]) {
    return match[1];
  }

  if (/^[a-zA-Z0-9-_]+$/.test(sheetUrlOrId)) {
    return sheetUrlOrId;
  }

  throw new Error('Link do Google Sheets invalido.');
}

function getSingleValue(values: unknown[][] | undefined | null): string {
  const value = values?.[0]?.[0];

  if (value === undefined || value === null) {
    return '';
  }

  return String(value).trim();
}

function parseNumber(value: string): number {
  if (!value) return 0;
  
  const normalized = value
    .replace(/[^\d,.-]/g, '')
    .replace(/\./g, '')
    .replace(',', '.');

  const parsed = Number(normalized);

  return Number.isFinite(parsed) ? parsed : 0;
}

function parseOptionalNumber(value: string): number | null {
  if (!value) {
    return null;
  }

  const parsed = parseNumber(value);

  return Number.isFinite(parsed) ? parsed : null;
}

function getFriendlyGoogleSheetsError(error: any): string {
  const status = error?.code || error?.response?.status;
  const message = error?.message ?? '';

  if (status === 403 || status === 401) {
    return 'Nao consegui ler essa planilha. Verifique se ela esta publica como "qualquer pessoa com o link pode visualizar".';
  }

  if (status === 404) {
    return 'Planilha nao encontrada. Verifique se o link esta correto.';
  }

  if (message.includes('Unable to parse range') || status === 400) {
    return 'Nao consegui encontrar uma das abas ou celulas esperadas na planilha.';
  }

  return `Erro ao ler a planilha: ${message || String(error)}`;
}

export async function readCharacterLogSheet(sheetUrl: string): Promise<CharacterLogSheetData> {
  const apiKey = process.env.GOOGLE_SHEETS_API_KEY;

  if (!apiKey) {
    throw new Error('GOOGLE_SHEETS_API_KEY nao foi definido no .env');
  }

  const spreadsheetId = extractSpreadsheetId(sheetUrl);

  const sheets = google.sheets({
    version: 'v4',
    auth: apiKey,
  });

  try {
    const response = await sheets.spreadsheets.values.batchGet({
      spreadsheetId,
      ranges: [
        'LOG!C6', // Nome do personagem
        'LOG!R25', // Rank
        'LOG!T5', // Classe
        'LOG!AL6', // Nivel
        'LOG!AE7', // Aventuras jogadas
        'Aventuras!J3', // Missão 1
        'Aventuras!W5', // Valor 1
        'Aventuras!J18', // Missão 2
        'Aventuras!W20', // Valor 2
        'Aventuras!J33', // Missão 3
        'Aventuras!W35', // Valor 3
        'Aventuras!J48', // Missão 4
        'Aventuras!W50', // Valor 4
        'Aventuras!J63', // Missão 5
        'Aventuras!W65', // Valor 5
      ],
      valueRenderOption: 'FORMATTED_VALUE',
      dateTimeRenderOption: 'FORMATTED_STRING',
    });

    const valueRanges = response.data.valueRanges ?? [];

    const characterName = getSingleValue(valueRanges[0]?.values);
    const rankName = getSingleValue(valueRanges[1]?.values);
    const className = getSingleValue(valueRanges[2]?.values);
    const levelRaw = getSingleValue(valueRanges[3]?.values);
    const adventuresPlayedRaw = getSingleValue(valueRanges[4]?.values);
    
    const missingFields: string[] = [];
    if (!characterName) missingFields.push('Nome (LOG!C6)');
    if (!rankName) missingFields.push('Rank (LOG!R25)');
    if (!className) missingFields.push('Classe (LOG!T5)');

    if (missingFields.length > 0) {
      throw new Error(`Nao consegui ler as seguintes celulas: ${missingFields.join(', ')}. Confira o formato da planilha.`);
    }

    const starterSlots = [
      { missionName: getSingleValue(valueRanges[5]?.values), value: getSingleValue(valueRanges[6]?.values) },
      { missionName: getSingleValue(valueRanges[7]?.values), value: getSingleValue(valueRanges[8]?.values) },
      { missionName: getSingleValue(valueRanges[9]?.values), value: getSingleValue(valueRanges[10]?.values) },
      { missionName: getSingleValue(valueRanges[11]?.values), value: getSingleValue(valueRanges[12]?.values) },
      { missionName: getSingleValue(valueRanges[13]?.values), value: getSingleValue(valueRanges[14]?.values) },
    ];

    const validStarterAdventures = starterSlots.filter((slot) => {
      if (hasIgnoredStarterTerm(slot.missionName)) {
        return false;
      }

      return parseNumber(slot.value) !== 0;
    }).length;

    return {
      spreadsheetId,
      characterName,
      rankName,
      className,
      level: parseOptionalNumber(levelRaw),
      adventuresPlayed: parseNumber(adventuresPlayedRaw),
      validStarterAdventures,
    };
  } catch (error: any) {
    if (error?.message && error.message.includes('Nao consegui ler nome')) {
      throw error;
    }
    throw new Error(getFriendlyGoogleSheetsError(error));
  }
}
