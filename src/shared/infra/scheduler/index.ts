import { PrismaSchedulerProvider } from '@/shared/providers/SchedulerProvider/implementations/Prisma/PrismaSchedulerProvider';
import { WinstonLoggerProvider } from '@/shared/providers/LoggerProvider/implementations/WinstonLoggerProvider';

const schedulerLogger = new WinstonLoggerProvider({
  loggerFileDirectory: 'log',
  logFileName: 'log-scheduler-combined',
  errorLogFileName: 'log-scheduler-error',
  loggerLabel: 'SCHEDULER',
});

export const scheduler = new PrismaSchedulerProvider({
  processEveryMs: 30_000, // 30 segundos
  logger: schedulerLogger,
});
