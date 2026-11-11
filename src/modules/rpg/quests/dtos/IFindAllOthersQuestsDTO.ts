export type QuestStatus = 'idle' | 'running' | 'paused' | 'frozen' | 'finished';

export interface IFindAllOthersQuestsDTO {
  userId: string;
  searchTerm: string;
  questStatus?: QuestStatus[];
  options?: { limit?: number };
}
