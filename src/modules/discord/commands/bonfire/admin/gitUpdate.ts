import { SlashCommandBuilder } from '@discordjs/builders';
import { exec } from 'child_process';
import { promisify } from 'util';

import { IDiscordCommand } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';

const execAsync = promisify(exec);
let isUpdating = false;

const commandData = new SlashCommandBuilder()
  .setName('git-update')
  .setDescription('Atualiza o bot pelo Git e reinicia o processo');

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
  return cleanOutput.length > 1400 ? `${cleanOutput.slice(-1400)}` : cleanOutput;
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

      await interaction.editReply('Atualizando codigo via Git...');

      // Stash local changes (e.g. .env) before pulling
      await runCommand('git stash --include-untracked').catch(() => {});
      const gitOutput = await runCommand('git pull --ff-only');
      // Restore stashed changes after pull
      await runCommand('git stash pop').catch(() => {});
      await interaction.editReply(`Git atualizado:\n\`\`\`\n${formatOutput(gitOutput)}\n\`\`\`\nInstalando dependencias...`);

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
      bot.logger.log('error', 'git-update failed', error);

      const message = error?.stderr || error?.stdout || error?.message || String(error);
      await interaction.editReply({
        content: `Falha ao atualizar:\n\`\`\`\n${formatOutput(message)}\n\`\`\``,
      });
    }
  },
};

export default command;
