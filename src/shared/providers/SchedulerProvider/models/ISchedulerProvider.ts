import { Client as BotClient } from 'discord.js';

export interface ISchedulerProvider {
  start: () => Promise<void>;
  stop: () => Promise<void>;
  loadDefaultJobs: (data: any) => Promise<void>;
  runJob(jobName: string, data?: Record<string, unknown>): Promise<void>;
  setBotClient: (botClient: BotClient) => void;
  scheduleJob(jobName: string, when: string | Date, data?: Record<string, unknown>): Promise<void>;
  cancelJobs?(query: Record<string, unknown>): Promise<number>;
  // getJobs: (jobName: string) => Promise<Job>;
  // startJob: (jobName: string) => Promise<void>;
  // stoptJob: (jobName: string) => Promise<void>;
  // createJob: (
  //   jobName: string,
  //   handler: (job: any, cb: any) => Promise<void>,
  // ) => Promise<void>;
  // deleteJob: (jobName: string) => Promise<void>;
}
