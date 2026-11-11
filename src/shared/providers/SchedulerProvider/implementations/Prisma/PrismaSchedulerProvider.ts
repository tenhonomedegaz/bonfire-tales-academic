import { Client as BotClient } from 'discord.js';

import { ISchedulerProvider } from '@/shared/providers/SchedulerProvider/models/ISchedulerProvider';
import { ILoggerProvider } from '@/shared/providers/LoggerProvider/models/ILoggerProvider';
import { ValidadeMembersJob } from '@/modules/members/jobs/ValidadeMembersJob';
import { GrantAdminModerationMonthlyTokensJob } from '@/modules/members/jobs/GrantAdminModerationMonthlyTokensJob';
import { RollShopItemsJob } from '@/modules/rpg/jobs/RollShopItemsJob';
import { PublishQuestJob } from '@/modules/rpg/jobs/PublishQuestJob';
import { PublishDedicatedRankJob } from '@/modules/rpg/jobs/PublishDedicatedRankJob';
import { AutoQuestQueueJob } from '@/modules/rpg/jobs/AutoQuestQueueJob';
import { prisma } from '@/shared/infra/database/prisma';
import { nowInBrazil } from '@/shared/util/dateTime';

interface PrismaSchedulerConfig {
  logger: ILoggerProvider;
  processEveryMs?: number;
}

interface JobDefinition {
  handler: (jobData: any) => Promise<void>;
}

interface DefaultJobConfig {
  jobName: string;
  cronExpression: string;
  timezone: string;
  disabled?: boolean;
}

/**
 * Scheduler provider que usa Prisma/PostgreSQL em vez de Agenda/MongoDB.
 * 
 * Jobs recorrentes são avaliadas por cron expression a cada tick do processador.
 * Jobs one-off (schedule/runJob) são salvas na tabela SchedulerJob com nextRunAt
 * e executadas quando chega a hora.
 */
export class PrismaSchedulerProvider implements ISchedulerProvider {
  private botClient?: BotClient;
  private logger: ILoggerProvider;
  private jobDefinitions: Map<string, JobDefinition> = new Map();
  private processInterval?: ReturnType<typeof setInterval>;
  private processEveryMs: number;
  private defaultJobs: DefaultJobConfig[] = [];
  private isRunning = false;
  private lastRunRecurring: Map<string, boolean> = new Map();
  private lastRunMinuteStr = '';

  constructor(config: PrismaSchedulerConfig) {
    this.logger = config.logger;
    this.processEveryMs = config.processEveryMs ?? 60_000; // 1 minute default
  }

  setBotClient(botClient: BotClient): void {
    this.botClient = botClient;
  }

  /**
   * Verifica se uma cron expression bate com a data/hora atual.
   * Formato: "segundo minuto hora diaDoMes mês diaDaSemana"
   */
  private getTzDateParts(date: Date, timezone?: string) {
    if (!timezone) {
      return {
        minute: date.getMinutes(),
        hour: date.getHours(),
        day: date.getDate(),
        month: date.getMonth() + 1,
        year: date.getFullYear(),
        dayOfWeek: date.getDay(),
      };
    }

    let offsetMs = -3 * 60 * 60 * 1000; // Default to America/Sao_Paulo (UTC-3)

    try {
      const tzString = date.toLocaleString('en-US', { timeZone: timezone, timeZoneName: 'longOffset' });
      const match = tzString.match(/GMT([-+])(\d{1,2}):?(\d{2})?/);
      if (match) {
        const sign = match[1] === '-' ? -1 : 1;
        const hours = parseInt(match[2], 10);
        const minutes = match[3] ? parseInt(match[3], 10) : 0;
        offsetMs = sign * (hours * 60 + minutes) * 60 * 1000;
      }
    } catch (err) {
      // Ignore and keep America/Sao_Paulo offset
    }

    const adjustedDate = new Date(date.getTime() + offsetMs);

    return {
      minute: adjustedDate.getUTCMinutes(),
      hour: adjustedDate.getUTCHours(),
      day: adjustedDate.getUTCDate(),
      month: adjustedDate.getUTCMonth() + 1,
      year: adjustedDate.getUTCFullYear(),
      dayOfWeek: adjustedDate.getUTCDay(),
    };
  }

  /**
   * Verifica se uma cron expression bate com a data/hora atual.
   * Formato: "segundo minuto hora diaDoMes mês diaDaSemana"
   */
  private cronMatchesNow(cronExpression: string, timezone?: string): boolean {
    const spNow = nowInBrazil();

    const parts = cronExpression.split(' ');
    if (parts.length !== 6) return false;

    const [, min, hour, dayOfMonth, month, dayOfWeek] = parts;

    const matches = (pattern: string, value: number): boolean => {
      if (pattern === '*') return true;
      // Handle ranges and lists if needed
      return pattern.split(',').some(p => parseInt(p, 10) === value);
    };

    const tzParts = this.getTzDateParts(spNow, timezone);

    return (
      matches(min, tzParts.minute) &&
      matches(hour, tzParts.hour) &&
      matches(dayOfMonth, tzParts.day) &&
      matches(month, tzParts.month) &&
      matches(dayOfWeek, tzParts.dayOfWeek)
    );
  }

  async start(): Promise<void> {
    if (!this.botClient) {
      throw new Error('[Scheduler] botClient was not set. Call setBotClient() BEFORE start().');
    }

    try {
      /* ===================== JOB DEFINITIONS ===================== */

      this.defineJob(ValidadeMembersJob.jobName, async (jobData) => {
        const job = new ValidadeMembersJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      this.defineJob(GrantAdminModerationMonthlyTokensJob.jobName, async (jobData) => {
        const job = new GrantAdminModerationMonthlyTokensJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      this.defineJob(PublishQuestJob.jobName, async (jobData) => {
        const job = new PublishQuestJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      this.defineJob(AutoQuestQueueJob.jobName, async (jobData) => {
        const job = new AutoQuestQueueJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      this.defineJob(RollShopItemsJob.jobName, async (jobData) => {
        const job = new RollShopItemsJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      this.defineJob(PublishDedicatedRankJob.jobName, async (jobData) => {
        const job = new PublishDedicatedRankJob();
        await job.execute({ botClient: this.botClient!, logger: this.logger, jobData });
      });

      /* ===================== START PROCESSING ===================== */

      this.isRunning = true;

      // Process one-off jobs from the database every interval
      this.processInterval = setInterval(() => {
        this.processScheduledJobs().catch((err) => {
          this.logger.log('error', '[SCHEDULER] Erro ao processar jobs:', err);
        });
      }, this.processEveryMs);

      // Log all registered default jobs
      this.defaultJobs.forEach((j) => {
        this.logger.log(
          'info',
          `[SCHEDULER] Recurring job: ${j.jobName} cron=${j.cronExpression} disabled=${!!j.disabled}`,
        );
      });

      // Log all one-off jobs from the database
      const dbJobs = await prisma.schedulerJob.findMany();
      dbJobs.forEach((j) => {
        this.logger.log('info', `[SCHEDULER] DB job: ${j.name} nextRunAt=${j.nextRunAt}`);
      });

      this.logger.log('info', 'Scheduler initialized successfully!');
    } catch (error) {
      this.logger.log('error', 'Scheduler initialization error:', error);
      throw error;
    }
  }

  private defineJob(jobName: string, handler: (jobData: any) => Promise<void>): void {
    this.jobDefinitions.set(jobName, { handler });
  }

  private isProcessing = false;

  /**
   * Processa jobs one-off do banco de dados cujo nextRunAt já passou.
   * Também avalia as cron expressions das jobs recorrentes.
   */
  private async processScheduledJobs(): Promise<void> {
    if (!this.isRunning) return;
    if (this.isProcessing) return;
    this.isProcessing = true;

    try {
      // 1. Process recurring cron jobs
      const spNow = nowInBrazil();
      const tzParts = this.getTzDateParts(spNow, 'America/Sao_Paulo');
      const currentMinuteStr = `${tzParts.year}-${tzParts.month}-${tzParts.day}-${tzParts.hour}-${tzParts.minute}`;

      if (this.lastRunMinuteStr !== currentMinuteStr) {
        this.lastRunRecurring.clear();
        this.lastRunMinuteStr = currentMinuteStr;
      }

      for (const defaultJob of this.defaultJobs) {
        if (defaultJob.disabled) continue;
        if (!this.cronMatchesNow(defaultJob.cronExpression, defaultJob.timezone)) continue;

        const runKey = `${defaultJob.jobName}_${(defaultJob as any).guildId}`;
        if (this.lastRunRecurring.has(runKey)) {
          continue;
        }
        this.lastRunRecurring.set(runKey, true);

        const definition = this.jobDefinitions.get(defaultJob.jobName);
        if (!definition) continue;

        this.logger.log('info', `[SCHEDULER] Cron job ${defaultJob.jobName} starting`);
        try {
          // Extract guildId from the default job config (stored via loadDefaultJobs)
          await definition.handler({ guildId: (defaultJob as any).guildId });
          this.logger.log('info', `[SCHEDULER] Cron job ${defaultJob.jobName} finished`);
        } catch (error) {
          this.logger.log('error', `[SCHEDULER] Cron job ${defaultJob.jobName} failed:`, error);
        }
      }

      // 2. Process one-off scheduled jobs from the database
      const now = nowInBrazil();
      const pendingJobs = await prisma.schedulerJob.findMany({
        where: { nextRunAt: { lte: now } },
      });

      for (const job of pendingJobs) {
        const definition = this.jobDefinitions.get(job.name);
        if (!definition) {
          this.logger.log('warn', `[SCHEDULER] No handler for job: ${job.name}, skipping`);
          continue;
        }

        this.logger.log('info', `[SCHEDULER] Job ${job.name} starting`);
        try {
          const jobData = (job.data as any) ?? {};
          await definition.handler(jobData);
          this.logger.log('info', `[SCHEDULER] Job ${job.name} finished`);

          // Remove after execution (one-off jobs)
          await prisma.schedulerJob.delete({ where: { id: job.id } });
        } catch (error) {
          this.logger.log('error', `[SCHEDULER] Job ${job.name} failed:`, error);
          // On failure, push nextRunAt 5 minutes into the future to retry
          try {
            await prisma.schedulerJob.update({
              where: { id: job.id },
              data: { nextRunAt: new Date(nowInBrazil().getTime() + 5 * 60 * 1000) },
            });
          } catch (updateError) {
            this.logger.log('error', `[SCHEDULER] Job ${job.name} failed to update nextRunAt:`, updateError);
          }
        }
      }
    } finally {
      this.isProcessing = false;
    }
  }

  async loadDefaultJobs(data: { guildId: string }): Promise<void> {
    // Remove existing default jobs for this guildId to avoid duplicates
    this.defaultJobs = this.defaultJobs.filter((job) => (job as any).guildId !== data.guildId);

    const jobsForGuild: DefaultJobConfig[] = [
      {
        jobName: ValidadeMembersJob.jobName,
        cronExpression: '0 0,10,20,30,40,50 * * * *',
        timezone: 'America/Sao_Paulo',
        ...data,
      },
      {
        jobName: GrantAdminModerationMonthlyTokensJob.jobName,
        cronExpression: '0 0 12 1 * *',
        timezone: 'America/Sao_Paulo',
        ...data,
      },
      {
        jobName: RollShopItemsJob.jobName,
        cronExpression: '0 0 5 * * 1',
        timezone: 'America/Sao_Paulo',
        disabled: true,
        ...data,
      },
      {
        jobName: PublishDedicatedRankJob.jobName,
        cronExpression: '0 59 23 * * 1',
        timezone: 'America/Sao_Paulo',
        ...data,
      },
    ];

    this.defaultJobs.push(...jobsForGuild);
  }

  async runJob(jobName: string, data: Record<string, unknown> = {}): Promise<void> {
    const definition = this.jobDefinitions.get(jobName);
    if (definition) {
      this.logger.log('info', `[SCHEDULER] Running job ${jobName} immediately`);
      try {
        await definition.handler(data);
      } catch (err) {
        this.logger.log('error', `[SCHEDULER] Immediate job execution failed: ${jobName}`, err);
        throw err;
      }
      return;
    }

    // Execute immediately by saving with nextRunAt = now
    await prisma.schedulerJob.create({
      data: {
        name: jobName,
        data: data as any,
        nextRunAt: nowInBrazil(),
      },
    });
  }

  async scheduleJob(jobName: string, when: string | Date, data: Record<string, unknown> = {}): Promise<void> {
    const nextRunAt = typeof when === 'string' ? new Date(when) : when;

    await prisma.schedulerJob.create({
      data: {
        name: jobName,
        data: data as any,
        nextRunAt,
      },
    });
  }

  async cancelJobs(query: Record<string, unknown>): Promise<number> {
    // Build a where clause from the query
    const where: any = {};

    if (query.name) {
      where.name = query.name as string;
    }

    // Handle data field queries like { 'data.questId': 'xxx' }
    // For Prisma JSON filtering, we need to use path-based queries
    const dataFilters: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(query)) {
      if (key.startsWith('data.')) {
        const dataKey = key.replace('data.', '');
        dataFilters[dataKey] = value;
      }
    }

    if (Object.keys(dataFilters).length > 0) {
      // Find all jobs and filter in-memory for JSON data matching
      const allJobs = await prisma.schedulerJob.findMany({ where });
      const toDelete: string[] = [];

      for (const job of allJobs) {
        const jobData = (job.data as any) ?? {};
        const matches = Object.entries(dataFilters).every(
          ([key, value]) => jobData[key] === value,
        );
        if (matches) {
          toDelete.push(job.id);
        }
      }

      if (toDelete.length > 0) {
        await prisma.schedulerJob.deleteMany({
          where: { id: { in: toDelete } },
        });
      }

      return toDelete.length;
    }

    const result = await prisma.schedulerJob.deleteMany({ where });
    return result.count;
  }

  async stop(): Promise<void> {
    this.isRunning = false;
    if (this.processInterval) {
      clearInterval(this.processInterval);
      this.processInterval = undefined;
    }
  }
}
