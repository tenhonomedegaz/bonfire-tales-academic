import { QuestPlayer, QuestStatus } from '@/modules/rpg/quests/entities/Quest';

export interface ICreateQuestDTO {
  guildId: string;
  name: string;
  description: string;
  questDate: Date;
  playersAmount: number;
  rules: string;
  tags?: string[];
  type: string;
  tableUrl: string;
  questMaster: string;
  allowedRanks: string[];
  mandatoryPlayers?: string[];
  highPriorityPlayers: string[];
  questPlayers?: QuestPlayer[];
  createdBy: string;
  channelId?: string | null;
  isPublished?: boolean;
  status?: QuestStatus;
  dedicatedRankId?: string;
}
