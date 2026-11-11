import { WinstonLoggerProvider } from '@/shared/providers/LoggerProvider/implementations/WinstonLoggerProvider';

export const logger = new WinstonLoggerProvider({
  loggerFileDirectory: 'log',
  logFileName: 'log-combined',
  errorLogFileName: 'log-error',
  loggerLabel: 'BOT',
});
