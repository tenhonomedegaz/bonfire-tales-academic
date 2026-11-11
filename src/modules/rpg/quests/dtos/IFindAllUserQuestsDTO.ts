export type QuestStatus = 'idle' | 'running' | 'paused' | 'frozen' | 'finished';

export interface IFindAllUserQuestsDTO {
  userId: string;
  searchTerm: string;
  questStatus?: QuestStatus[];
  options?: { limit?: number };
  questMaster?: string;
}
