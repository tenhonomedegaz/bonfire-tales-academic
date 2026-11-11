import { SlashCommandBuilder } from '@discordjs/builders';
import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';

import { IDiscordCommand } from '@/modules/discord/types';
import { isBotRootAdmin } from '@/modules/discord/util';

const execAsync = promisify(exec);

const getSiteDir = () => {
  if (process.env.BONFIRE_SITE_DIR) {
    return path.resolve(process.env.BONFIRE_SITE_DIR);
  }
  const p1 = path.resolve(process.cwd(), '../BonfireSite-main');
  const p2 = path.resolve(process.cwd(), '../BonfireSite');
  return fs.existsSync(p2) && !fs.existsSync(p1) ? p2 : p1;
};

const SITE_DIR = getSiteDir();
const SITE_LOG_FILE = path.join(SITE_DIR, 'site_console.log');

const commandData = new SlashCommandBuilder()
  .setName('site')
  .setDescription('Gerencia o site Django (BonfireSite)')
  .addSubcommand((subcommand) =>
    subcommand
      .setName('console')
      .setDescription('Mostra os logs recentes do site')
      .addIntegerOption((option) =>
        option
          .setName('linhas')
          .setDescription('Quantidade de linhas para mostrar (padrao 30)')
          .setMinValue(5)
          .setMaxValue(80)
          .setRequired(false),
      )
  )
  .addSubcommand((subcommand) =>
    subcommand
      .setName('update')
      .setDescription('Baixa atualizacoes do github (branch dev) e reinicia o site')
  )
  .addSubcommand((subcommand) =>
    subcommand
      .setName('force-update')
      .setDescription('Limpa o cache do Python, descarta conflitos e forca atualizacao (origin dev)')
  )
  .addSubcommand((subcommand) =>
    subcommand
      .setName('restart')
      .setDescription('Reinicia o servidor do site')
  )
  .addSubcommand((subcommand) =>
    subcommand
      .setName('stop')
      .setDescription('Desliga o servidor do site')
  );

async function runCommand(cmd: string, cwd: string): Promise<string> {
  const { stdout, stderr } = await execAsync(cmd, {
    cwd,
    timeout: 300000, // 5 minutos de timeout para comandos como npm/pip install ou clone
    windowsHide: true,
    maxBuffer: 1024 * 1024,
  });
  return [stdout, stderr].filter(Boolean).join('\n').trim();
}

function formatOutput(output: string): string {
  if (!output) return 'ok';
  const clean = output.trim();
  return clean.length > 1400 ? `...${clean.slice(-1400)}` : clean;
}

function readSiteLog(linesAmount: number): string {
  if (!fs.existsSync(SITE_LOG_FILE)) {
    return 'Arquivo de log do site nao encontrado.';
  }

  const content = fs.readFileSync(SITE_LOG_FILE, 'utf8');
  const lines = content.trimEnd().split(/\r?\n/).slice(-linesAmount);
  const output = lines.join('\n').trim();

  if (!output) return 'Log do site vazio.';
  return output.length > 1900 ? `...${output.slice(-1900)}` : output;
}

let isActionRunning = false;

const command: IDiscordCommand = {
  commandData,
  allowedRoles: [], // Somente root admins via validacao interna
  cooldown: 5000,
  rootAdminOnly: true,

  async execute(bot, interaction) {
    if (!isBotRootAdmin(interaction.user.id)) {
      await interaction.reply({
        content: 'Voce nao tem permissao para usar este comando.',
        ephemeral: true,
      });
      return;
    }

    const subcommand = interaction.options.getSubcommand();

    if (subcommand === 'console') {
      await interaction.deferReply({ ephemeral: true });
      const linhas = interaction.options.getInteger('linhas') ?? 30;
      const logOutput = readSiteLog(linhas);
      await interaction.editReply(`Console do Site (ultimas ${linhas} linhas):\n\`\`\`\n${logOutput}\n\`\`\``);
      return;
    }

    if (isActionRunning) {
      await interaction.reply({
        content: 'Ja existe uma acao de gerenciamento do site em andamento.',
        ephemeral: true,
      });
      return;
    }

    try {
      await interaction.deferReply({ ephemeral: true });
      isActionRunning = true;

      if (subcommand === 'stop') {
        if (!fs.existsSync(SITE_DIR)) {
          throw new Error(`Pasta do site nao encontrada em: ${SITE_DIR}`);
        }
        await interaction.editReply('Encerrando servidor Django...');
        const out = await runCommand('cmd.exe /c stop_server.bat', SITE_DIR);
        await interaction.editReply(`Servidor encerrado:\n\`\`\`\n${formatOutput(out)}\n\`\`\``);
      }

      else if (subcommand === 'update') {
        if (!fs.existsSync(SITE_DIR)) {
          await interaction.editReply('A pasta do site não foi encontrada.');
          return;
        }

        await interaction.editReply('1. Puxando alteracoes do Git (origin dev)...');
        // Protect .env from git stash
        const siteEnvPath = path.join(SITE_DIR, '.env');
        const siteEnvBackup = path.join(SITE_DIR, '.env.bak');
        if (fs.existsSync(siteEnvPath)) {
          fs.copyFileSync(siteEnvPath, siteEnvBackup);
        }
        
        await runCommand('git rm --cached bonfas_classes.db -f', SITE_DIR).catch(() => { });
        await runCommand('git stash', SITE_DIR).catch(() => { });
        const gitOutput = await runCommand('git pull origin dev --ff-only', SITE_DIR);
        await runCommand('git stash pop', SITE_DIR).catch(() => { });

        // Restore protected files
        if (fs.existsSync(siteEnvBackup)) {
          fs.copyFileSync(siteEnvBackup, siteEnvPath);
          fs.unlinkSync(siteEnvBackup);
        }

        if (!fs.existsSync(path.join(SITE_DIR, '.venv'))) {
          await interaction.followUp({ content: '⚠️ Erro: A pasta `.venv` não existe.', ephemeral: true });
          return;
        }

        await interaction.editReply(`Git atualizado:\n\`\`\`\n${formatOutput(gitOutput)}\n\`\`\`\n2. Atualizando dependencias (pip)...`);
        const pipOutput = await runCommand('.venv\\Scripts\\pip install -r requirements.txt', SITE_DIR);

        await interaction.editReply(`Dependencias atualizadas:\n\`\`\`\n${formatOutput(pipOutput)}\n\`\`\`\n3. Rodando migrações...`);
        const migrateOutput = await runCommand('.venv\\Scripts\\python.exe manage.py migrate --noinput', SITE_DIR);

        await interaction.editReply(`Migracoes concluidas:\n\`\`\`\n${formatOutput(migrateOutput)}\n\`\`\`\n4. Coletando estáticos...`);
        const staticOutput = await runCommand('.venv\\Scripts\\python.exe manage.py collectstatic --noinput', SITE_DIR);

        await interaction.editReply(`Estaticos coletados:\n\`\`\`\n${formatOutput(staticOutput)}\n\`\`\`\n6. Reiniciando servidor...`);

        await runCommand('cmd.exe /c stop_server.bat', SITE_DIR).catch(() => { });
        const { spawn } = require('child_process');
        const child = spawn('cmd.exe', ['/c', 'start_server_silent.bat'], {
          cwd: SITE_DIR,
          detached: true,
          stdio: 'ignore'
        });
        child.unref();

        await interaction.followUp({
          content: 'Update do site finalizado com sucesso! O servidor esta sendo reiniciado.',
          ephemeral: true,
        });
      }

      else if (subcommand === 'restart') {
        if (!fs.existsSync(SITE_DIR)) {
          throw new Error(`Pasta do site nao encontrada em: ${SITE_DIR}`);
        }
        await interaction.editReply('Reiniciando servidor Django...');
        await runCommand('cmd.exe /c stop_server.bat', SITE_DIR).catch(() => { });
        const { spawn } = require('child_process');
        const child = spawn('cmd.exe', ['/c', 'start_server_silent.bat'], {
          cwd: SITE_DIR,
          detached: true,
          stdio: 'ignore'
        });
        child.unref();

        await interaction.followUp({
          content: '✅ Servidor reiniciado com sucesso!',
          ephemeral: true,
        });
      }

      else if (subcommand === 'force-update') {
        if (!fs.existsSync(SITE_DIR)) {
          await interaction.editReply('A pasta do site não foi encontrada.');
          return;
        }

        await interaction.editReply('Forcando atualização...\n1. Limpando arquivos de cache...');
        await runCommand('powershell -Command "Get-ChildItem -Path . -Include *.pyc, __pycache__ -Recurse -Force | Remove-Item -Recurse -Force"', SITE_DIR).catch(() => { });

        await interaction.editReply('2. Protegendo configurações e baixando repositório...');
        // Protect .env from git reset --hard
        const siteEnvPath = path.join(SITE_DIR, '.env');
        const siteEnvBackup = path.join(SITE_DIR, '.env.bak');
        if (fs.existsSync(siteEnvPath)) {
          fs.copyFileSync(siteEnvPath, siteEnvBackup);
        }
        // Protect the database file from git reset --hard
        const dbPath = path.join(SITE_DIR, 'bonfas_classes.db');
        const dbBackupPath = path.join(SITE_DIR, 'bonfas_classes.db.bak');
        if (fs.existsSync(dbPath)) {
          fs.copyFileSync(dbPath, dbBackupPath);
        }

        await runCommand('git fetch --all', SITE_DIR);
        const gitOutput = await runCommand('git reset --hard origin/dev', SITE_DIR);

        // Restore protected files after reset
        if (fs.existsSync(siteEnvBackup)) {
          fs.copyFileSync(siteEnvBackup, siteEnvPath);
          fs.unlinkSync(siteEnvBackup);
        }
        if (fs.existsSync(dbBackupPath)) {
          fs.copyFileSync(dbBackupPath, dbPath);
          fs.unlinkSync(dbBackupPath);
        }

        if (!fs.existsSync(path.join(SITE_DIR, '.venv'))) {
          await interaction.followUp({ content: '⚠️ Erro: A pasta `.venv` não existe.', ephemeral: true });
          return;
        }

        await interaction.editReply(`Git forcado:\n\`\`\`\n${formatOutput(gitOutput)}\n\`\`\`\n3. Atualizando dependencias (pip)...`);
        const pipOutput = await runCommand('.venv\\Scripts\\pip install -r requirements.txt', SITE_DIR);

        await interaction.editReply(`Dependencias OK:\n\`\`\`\n${formatOutput(pipOutput)}\n\`\`\`\n4. Aplicando migracoes...`);
        const migrateOutput = await runCommand('.venv\\Scripts\\python.exe manage.py migrate --noinput', SITE_DIR);

        await interaction.editReply(`Migracoes OK:\n\`\`\`\n${formatOutput(migrateOutput)}\n\`\`\`\n5. Coletando estáticos...`);
        const staticOutput = await runCommand('.venv\\Scripts\\python.exe manage.py collectstatic --noinput', SITE_DIR);

        await interaction.editReply(`Estaticos OK:\n\`\`\`\n${formatOutput(staticOutput)}\n\`\`\`\n6. Reiniciando servidor...`);

        await runCommand('cmd.exe /c stop_server.bat', SITE_DIR).catch(() => { });
        const { spawn } = require('child_process');
        const child = spawn('cmd.exe', ['/c', 'start_server_silent.bat'], {
          cwd: SITE_DIR,
          detached: true,
          stdio: 'ignore'
        });
        child.unref();

        await interaction.followUp({
          content: '✅ **Force-Update** do site finalizado com sucesso! O servidor está sendo reiniciado agora mesmo.',
          ephemeral: true,
        });
      }

    } catch (error: any) {
      bot.logger.log('error', `site ${subcommand} failed`, error);
      const message = error?.stderr || error?.stdout || error?.message || String(error);
      await interaction.editReply({
        content: `Falha ao executar \`/site ${subcommand}\`:\n\`\`\`\n${formatOutput(message)}\n\`\`\``,
      });
    } finally {
      isActionRunning = false;
    }
  },
};

export default command;
