import 'reflect-metadata';

import { env } from '@/shared/env';
import { registerDependencies } from '@/shared/container';
import { DiscordBot } from '@/modules/discord/DiscordBot';
import { syncTimeOffset } from '@/shared/util/dateTime';
import { prisma } from '@/shared/infra/database/prisma';
import { logger } from '@/shared/infra/logger';
import { scheduler } from '@/shared/infra/scheduler';
import { startBackupRoutine } from '@/shared/infra/bot/backupRoutine';
// import { store } from '@/shared/infra/store';

const discordBot = new DiscordBot({
  botName: env.DISCORD_BOT_NAME,
  botToken: env.DISCORD_BOT_TOKEN,
  clientId: env.DISCORD_CLIENT_ID,
  logger,
  scheduler,
  // store,
});

async function run() {
  try {
    registerDependencies();

    // Connect to PostgreSQL via Prisma
    await prisma.$connect();
    
    // Sync machine time with Discord time
    await syncTimeOffset();

    // test server
    // await discordBot.syncGuildCommands({ discordGuildId: '826825529109118976' });

    // await discordBot.syncGuildCommands({ discordGuildId: '803349484884721674' });
    // await discordBot.deleteGuildCommands({ discordGuildId: '803349484884721674' });

    await discordBot.startUp();
    
    // Inicia rotina de backups periódicos em segundo plano
    startBackupRoutine();
  } catch (error) {
    logger.log('error', 'Bot startup error', error);

    await discordBot.shutDown();
  }
}

run();

// For any unhandled errors
process.on('uncaughtException', (error) => {
  logger.log('error', 'uncaughtException', error);
});

process.on('unhandledRejection', (error) => {
  logger.log('error', 'unhandledRejection', error);
});

// Enable graceful stop
process.once('SIGINT', () => discordBot.shutDown());
process.once('SIGTERM', () => discordBot.shutDown());
