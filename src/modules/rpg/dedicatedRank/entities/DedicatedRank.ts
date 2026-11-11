export interface RankReward {
  rankName: string;
  position: number;
  questsCount: number;
  rewardPerProgression: number;
  maxTotalReward: number;
}

export class DedicatedRank {
  id?: string;
  guildId: string;
  rankings: RankReward[];
  validFrom: Date;
  validUntil: Date;
  isActive: boolean;
  isPriorityLocked: boolean;
  priorityRankName?: string;
  createdAt?: Date;
  updatedAt?: Date;

  constructor(props: {
    id?: string;
    guildId: string;
    rankings: RankReward[];
    validFrom: Date;
    validUntil: Date;
    isActive: boolean;
    isPriorityLocked?: boolean;
    priorityRankName?: string;
    createdAt?: Date;
    updatedAt?: Date;
  }) {
    this.id = props.id;
    this.guildId = props.guildId;
    this.rankings = props.rankings;
    this.validFrom = props.validFrom;
    this.validUntil = props.validUntil;
    this.isActive = props.isActive;
    this.isPriorityLocked = props.isPriorityLocked || false;
    this.priorityRankName = props.priorityRankName;
    this.createdAt = props.createdAt;
    this.updatedAt = props.updatedAt;
  }
}
