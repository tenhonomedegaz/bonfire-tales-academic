import { exec } from 'child_process';
import { promisify } from 'util';
import fs from 'fs';
import path from 'path';
import { logger } from '@/shared/infra/logger';

const execAsync = promisify(exec);

export async function createDatabaseBackup() {
  try {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const backupDir = path.resolve(process.cwd(), 'backups');
    
    if (!fs.existsSync(backupDir)) {
      fs.mkdirSync(backupDir, { recursive: true });
    }

    const filename = `backup-${timestamp}.sql`;
    const filepath = path.join(backupDir, filename);

    // Pegamos a URL do banco (tentamos POSTGRES_URL, DATABASE_URL, ou valor padrão)
    const dbUrl = process.env.POSTGRES_URL || process.env.DATABASE_URL || 'postgresql://postgres:bonfire@localhost:5432/postgres?schema=public';

    logger.log('info', `[Backup] Iniciando backup do PostgreSQL para ${filename}...`);

    // Usa pg_dump para fazer backup
    // A flag --clean --if-exists garante que ao restaurar ele limpe os dados anteriores sem conflito
    await execAsync(`pg_dump --clean --if-exists "${dbUrl}" > "${filepath}"`);

    logger.log('info', `[Backup] Backup concluído com sucesso: ${filepath}`);

    // Limpeza: manter apenas os últimos 10 backups para não lotar o disco
    const files = fs.readdirSync(backupDir)
      .filter(f => f.startsWith('backup-') && f.endsWith('.sql'))
      .map(f => ({ name: f, filepath: path.join(backupDir, f), time: fs.statSync(path.join(backupDir, f)).mtime.getTime() }))
      .sort((a, b) => b.time - a.time);

    if (files.length > 10) {
      const toDelete = files.slice(10);
      for (const file of toDelete) {
        fs.unlinkSync(file.filepath);
        logger.log('info', `[Backup] Backup antigo deletado: ${file.name}`);
      }
    }

    // Opcional: Para commitar numa branch, descomente o código abaixo:
    /*
    await execAsync(`git checkout -B db-backups`);
    await execAsync(`git add "${filepath}"`);
    await execAsync(`git commit -m "chore: backup ${timestamp}"`);
    await execAsync(`git push origin db-backups`);
    await execAsync(`git checkout main`);
    */

  } catch (error) {
    logger.log('error', '[Backup] Erro ao realizar backup do banco de dados:', error);
  }
}

export function startBackupRoutine() {
  // Configurado para rodar a cada 6 horas
  const intervalMs = 6 * 60 * 60 * 1000;
  
  // Roda o primeiro backup 5 minutos após o bot ligar
  setTimeout(() => {
    createDatabaseBackup();
  }, 5 * 60 * 1000);

  // E depois roda continuamente no intervalo
  setInterval(() => {
    createDatabaseBackup();
  }, intervalMs);
}
