import { SlashCommandBuilder } from '@discordjs/builders';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

import { IDiscordCommand } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';

const execAsync = promisify(exec);
let isUpdating = false;

const commandData = new SlashCommandBuilder()
  .setName('git-force-update')
  .setDescription('Forca o bot a ficar igual ao GitHub e reinicia o processo');

async function runCommand(command: string): Promise<string> {
  const { stdout, stderr } = await execAsync(command, {
    cwd: process.cwd(),
    timeout: 120000,
    windowsHide: true,
    maxBuffer: 1024 * 1024,
  });

  return [stdout, stderr].filter(Boolean).join('\n').trim();
}

function formatOutput(output: string): string {
  if (!output) {
    return 'ok';
  }

  const cleanOutput = output.trim();
  return cleanOutput.length > 1400 ? cleanOutput.slice(-1400) : cleanOutput;
}

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [],
  cooldown: 30000,
  rootAdminOnly: true,

  async execute(bot, interaction) {
    if (isUpdating) {
      await interaction.reply({
        content: 'Ja existe uma atualizacao em andamento.',
        ephemeral: true,
      });
      return;
    }

    try {
      await interaction.deferReply({ ephemeral: true });

      if (!isBotRootAdmin(interaction.user.id)) {
        await interaction.editReply({
          content: 'Voce nao tem permissao para usar este comando.',
        });
        return;
      }

      isUpdating = true;

      await interaction.editReply('Forcando atualizacao pelo GitHub...');

      // Protect .env from git reset --hard
      const envPath = path.join(process.cwd(), '.env');
      const envBackupPath = path.join(process.cwd(), '.env.bak');
      if (fs.existsSync(envPath)) {
        fs.copyFileSync(envPath, envBackupPath);
      }

      const fetchOutput = await runCommand('git fetch origin');
      await interaction.editReply(`Fetch concluido:\n\`\`\`\n${formatOutput(fetchOutput)}\n\`\`\`\nResetando para origin/master...`);

      const resetOutput = await runCommand('git reset --hard origin/master');

      // Restore .env after reset
      if (fs.existsSync(envBackupPath)) {
        fs.copyFileSync(envBackupPath, envPath);
        fs.unlinkSync(envBackupPath);
      }

      await interaction.editReply(`Reset concluido:\n\`\`\`\n${formatOutput(resetOutput)}\n\`\`\`\nInstalando dependencias...`);

      const installOutput = await runCommand('npm install');
      await interaction.editReply(`Dependencias atualizadas:\n\`\`\`\n${formatOutput(installOutput)}\n\`\`\`\nGerando build...`);

      const buildOutput = await runCommand('npm run build');
      await interaction.editReply(
        `Build finalizado:\n\`\`\`\n${formatOutput(buildOutput)}\n\`\`\`\nReiniciando o bot...`,
      );

      setTimeout(() => {
        process.exit(0);
      }, 3000);
    } catch (error: any) {
      isUpdating = false;
      bot.logger.log('error', 'git-force-update failed', error);

      const message = error?.stderr || error?.stdout || error?.message || String(error);
      await interaction.editReply({
        content: `Falha ao forcar atualizacao:\n\`\`\`\n${formatOutput(message)}\n\`\`\``,
      });
    }
  },
};

export default command;
