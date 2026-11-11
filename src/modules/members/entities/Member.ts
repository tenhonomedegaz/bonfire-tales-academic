export interface Member {
  id: string;
  discordUserId: string;
  discordUserTag: string;
  email: string;
  tokenSuperboost: number;
  tokenXpBoost: number;
  tokenMission: number;
  isModerator: boolean;
  createdAt: Date;
  updatedAt: Date;
}
