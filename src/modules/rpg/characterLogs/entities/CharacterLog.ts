export interface CharacterLog {
  id: string;
  discordUserId: string;
  discordUserTag: string;
  sheetUrl: string;
  spreadsheetId: string;
  characterName: string;
  rankName: string;
  className: string;
  level: number;
  adventuresPlayed: number;
  validStarterAdventures: number;
  isNovice: boolean;
  registeredBy: string;
  createdAt: Date;
  updatedAt: Date;
}
