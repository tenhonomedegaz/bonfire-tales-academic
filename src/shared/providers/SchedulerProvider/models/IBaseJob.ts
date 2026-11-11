import { Client } from 'discord.js';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';

export type BotClient = Client;

interface JobRequest {
  botClient: BotClient;
  logger: ILoggerProvider;
  jobData?: unknown;
}

interface IBaseJob {
  execute({ botClient, logger, jobData }: JobRequest): Promise<any>;
}

export { IBaseJob };
