export type QuestStatus = 'idle' | 'running' | 'paused' | 'frozen' | 'finished';

export type PlayerType = 'normal' | 'high-priority' | 'subscriber' | 'fill';

export interface QuestPlayer {
  userId: string;
  type: PlayerType;
  characterName?: string;
  class?: string;
  level?: number;
  characterUrl?: string;
  removedAt?: Date;
  removedWithReward?: boolean;
  rewardMinutes?: number;
  rewardAmount?: number;
  rewardFinalizedAt?: string;
  rewardSource?: 'quest_finish' | 'staff_override';
}

export interface QueuePlayer {
  userId: string;
  subscriptionDate: Date;
}

export interface ParticipationRequest {
  userId: string;
  characterName?: string;
  characterUrl: string;
  class: string;
  level: number;
  requestDate: Date;
  confirmedAt?: Date;
}

export type QuestTimeEventType = 'run' | 'pause' | 'freeze' | 'finish';
export interface QuestTimeEvent {
  eventType: QuestTimeEventType;
  userId: string;
  date: Date;
}

export interface Quest {
  id: string;
  guildId: string;
  channelId: string | null;
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
  mandatoryPlayers: string[];
  highPriorityPlayers: string[];
  subscribedPlayers: QueuePlayer[];
  participationRequests: ParticipationRequest[];
  questPlayers: QuestPlayer[];
  removedPlayers: string[];
  createdBy: string;
  isPublished: boolean;
  status: QuestStatus;
  timeEvents: QuestTimeEvent[];
  startDate: Date;
  endDate: Date;
  rewardAventurasOverride?: number;
  dedicatedRankId?: string; // Ranking dedicado que tava ativo quando a quest foi criada
  createdAt: Date;
  updatedAt: Date;
}
