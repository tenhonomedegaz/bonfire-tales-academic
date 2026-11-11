import { SlashCommandBuilder } from '@discordjs/builders';
import fs from 'fs';
import path from 'path';

import { IDiscordCommand } from '@/modules/discord/types';
import { bonfireRoles } from '@/config/bonfire';

const LOG_DIR = 'log';
const LOG_FILE_PATTERN = /(^|_)log-combined\.log$/;
const MAX_DISCORD_CONTENT_LENGTH = 1900;

const commandData = new SlashCommandBuilder()
  .setName('console')
  .setDescription('Mostra os logs recentes do bot')
  .addIntegerOption((option) =>
    option
      .setName('linhas')
      .setDescription('Quantidade de linhas para mostrar')
      .setMinValue(5)
      .setMaxValue(80)
      .setRequired(false),
  )
  .addBooleanOption((option) =>
    option
      .setName('live')
      .setDescription('Atualiza a mensagem automaticamente por alguns segundos')
      .setRequired(false),
  )
  .addIntegerOption((option) =>
    option
      .setName('segundos')
      .setDescription('Duracao do modo live')
      .setMinValue(10)
      .setMaxValue(120)
      .setRequired(false),
  );

function findLatestLogFile(): string | null {
  const logDir = path.resolve(process.cwd(), LOG_DIR);

  if (!fs.existsSync(logDir)) {
    return null;
  }

  const files = fs.readdirSync(logDir)
    .filter((fileName) => LOG_FILE_PATTERN.test(fileName))
    .map((fileName) => {
      const filePath = path.join(logDir, fileName);
      return {
        fileName,
        filePath,
        modifiedAt: fs.statSync(filePath).mtimeMs,
      };
    })
    .sort((a, b) => b.modifiedAt - a.modifiedAt);

  return files[0]?.filePath ?? null;
}

function tailLog(filePath: string, linesAmount: number): string {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.trimEnd().split(/\r?\n/).slice(-linesAmount);
  const output = lines.join('\n').trim();

  if (!output) {
    return 'Log vazio.';
  }

  return output.length > MAX_DISCORD_CONTENT_LENGTH
    ? output.slice(output.length - MAX_DISCORD_CONTENT_LENGTH)
    : output;
}

function formatLogMessage(filePath: string | null, linesAmount: number, live: boolean): string {
  if (!filePath) {
    return 'Nenhum arquivo de log encontrado ainda.';
  }

  const fileName = path.basename(filePath);
  const liveLabel = live ? ' | live' : '';
  const output = tailLog(filePath, linesAmount);

  return `Console (${fileName}, ultimas ${linesAmount} linhas${liveLabel}):\n\`\`\`\n${output}\n\`\`\``;
}

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [bonfireRoles.adminRoleName],
  cooldown: 5000,

  async execute(bot, interaction) {
    await interaction.deferReply({ ephemeral: true });

    const linesAmount = interaction.options.getInteger('linhas') ?? 30;
    const live = interaction.options.getBoolean('live') ?? false;
    const liveSeconds = interaction.options.getInteger('segundos') ?? 60;

    const logFile = findLatestLogFile();
    await interaction.editReply(formatLogMessage(logFile, linesAmount, live));

    if (!live || !logFile) {
      return;
    }

    const startedAt = Date.now();
    const interval = setInterval(async () => {
      try {
        const latestLogFile = findLatestLogFile();
        await interaction.editReply(formatLogMessage(latestLogFile, linesAmount, true));

        if (Date.now() - startedAt >= liveSeconds * 1000) {
          clearInterval(interval);
        }
      } catch (error) {
        clearInterval(interval);
        bot.logger.log('error', 'console live update failed', error);
      }
    }, 5000);
  },
};

export default command;
