import { createLogger, format, transports, Logger } from "winston";
import DailyRotateFile from "winston-daily-rotate-file";

import {
  ILoggerProvider,
  logLeveType,
} from "@/shared/providers/LoggerProvider/models/ILoggerProvider";
import { env } from "@/shared/env";

const { combine, timestamp, label, printf } = format;

interface ILoggerConfig {
  loggerFileDirectory: string;
  logFileName: string;
  errorLogFileName: string;
  loggerLabel: string;
}

export class WinstonLoggerProvider implements ILoggerProvider {
  private winstonLogger: Logger;

  constructor(private config: ILoggerConfig) {
    // Console format
    const consoleFormat = printf(({ level, message, label, timestamp }) => {
      return `${timestamp} [${label}] ${level.toUpperCase()}: ${message}`;
    });

    // File format
    const fileFormat = printf(({ level, message, timestamp }) => {
      return `${timestamp} [${level.toUpperCase()}]: ${message}`;
    });

    const devTransports = [
      new transports.Console({
        format: combine(
          label({ label: this.config.loggerLabel }),
          timestamp(),
          consoleFormat
        ),
      }),

      new transports.File({
        dirname: this.config.loggerFileDirectory,
        filename: `${this.config.errorLogFileName}.log`,
        level: "error",
      }),

      new transports.File({
        dirname: this.config.loggerFileDirectory,
        filename: `${this.config.logFileName}.log`,
        level: "info",
      }),
    ];

    const prodTransports = [
      new transports.Console({
        format: combine(
          label({ label: this.config.loggerLabel }),
          timestamp(),
          consoleFormat
        ),
      }),

      new DailyRotateFile({
        dirname: this.config.loggerFileDirectory,
        filename: `%DATE%_${this.config.errorLogFileName}.log`,
        datePattern: "YYYY-MM-DD",
        level: "error",
        maxFiles: "30d",
      }),

      new DailyRotateFile({
        dirname: this.config.loggerFileDirectory,
        filename: `%DATE%_${this.config.logFileName}.log`,
        datePattern: "YYYY-MM-DD",
        level: "info",
        maxFiles: "30d",
      }),
    ];

    this.winstonLogger = createLogger({
      level: env.NODE_ENV !== "production" ? "verbose" : "info",
      format: combine(timestamp(), fileFormat),
      transports: env.NODE_ENV === "production" ? prodTransports : devTransports,
    });
  }

  log(level: logLeveType, message: string, ...meta: any[]): void {
    this.winstonLogger.log(level, message, ...meta);
  }
}
