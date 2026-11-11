export interface SchedulerJob {
  id: string;
  name: string;
  data: any;
  nextRunAt: Date | null;

  // priority?: number;
  // type?: string;
  // repeatInterval?: string;
  // repeatTimezone?: string;
  // startDate?: Date;
  // endDate?: Date;
  // skipDays?: any;
  // lastModifiedBy?: string;
  // disabled?: boolean;
  // lockedAt?: Date;
  // lastRunAt?: Date;
  // lastFinishedAt?: Date;
}
