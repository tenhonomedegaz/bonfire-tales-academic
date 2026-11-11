import https from 'https';
import http from 'http';
import fs from 'fs';
import path from 'path';
import { parseISO } from 'date-fns';

const BONFIRE_TIMEZONE_OFFSET = '-03:00';
const BONFIRE_TIMEZONE = 'America/Sao_Paulo';

const OFFSET_FILE_NAME = '.time-offset.json';
const primaryPath = path.join(__dirname, '..', '..', '..', OFFSET_FILE_NAME);
const fallbackPath = path.join(process.cwd(), OFFSET_FILE_NAME);

export let timeOffsetMs = 0;

// Carrega o offset inicial do arquivo síncronamente
try {
  let loaded = false;
  for (const filePath of [primaryPath, fallbackPath]) {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      const data = JSON.parse(content);
      if (typeof data.offset === 'number') {
        timeOffsetMs = data.offset;
        console.log(`[TimeSync] Offset inicial carregado do arquivo (${filePath}): ${timeOffsetMs}ms`);
        loaded = true;
        break;
      }
    }
  }
  if (!loaded) {
    console.log('[TimeSync] Nenhum arquivo de offset encontrado. Usando offset inicial de 0ms.');
  }
} catch (err) {
  console.warn('[TimeSync] Erro ao carregar offset inicial do arquivo:', err);
}

let isIntervalStarted = false;

export async function syncTimeOffset() {
  const trusted = await trustedNow();
  if (trusted) {
    timeOffsetMs = trusted.getTime() - Date.now();
    console.log(`[TimeSync] Offset da máquina sincronizado: ${timeOffsetMs}ms (Horário oficial: ${trusted.toISOString()})`);
    
    // Salva o offset nos arquivos
    for (const filePath of [primaryPath, fallbackPath]) {
      try {
        fs.writeFileSync(
          filePath,
          JSON.stringify({ offset: timeOffsetMs, updatedAt: new Date().toISOString() }),
          'utf-8'
        );
      } catch (err) {
        // Ignora erros ao tentar escrever em caminhos específicos
      }
    }
  } else {
    console.warn(`[TimeSync] WARNING: Não foi possível obter o horário de fontes externas. O offset atual de ${timeOffsetMs}ms será mantido.`);
  }

  if (!isIntervalStarted) {
    isIntervalStarted = true;
    // Sincroniza periodicamente a cada 30 minutos
    setInterval(() => {
      syncTimeOffset().catch(err => console.error('[TimeSync] Erro no loop de sincronização:', err));
    }, 30 * 60 * 1000);
  }
}

function getBrazilDateParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: BONFIRE_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const valueByType = new Map(parts.map((part) => [part.type, part.value]));

  return {
    day: valueByType.get('day') ?? '01',
    month: valueByType.get('month') ?? '01',
    year: valueByType.get('year') ?? '1970',
    hour: valueByType.get('hour') ?? '00',
    minute: valueByType.get('minute') ?? '00',
    second: valueByType.get('second') ?? '00',
  };
}

export function toBrazilDateTimeISO(date: string, time: string): string {
  const [dd, MM, yyyy] = date.split('/');
  const [hh, mm] = time.split(':');

  return [
    yyyy,
    '-',
    MM.padStart(2, '0'),
    '-',
    dd.padStart(2, '0'),
    'T',
    hh.padStart(2, '0'),
    ':',
    mm.padStart(2, '0'),
    ':00',
    BONFIRE_TIMEZONE_OFFSET,
  ].join('');
}

export function parseBrazilDateTime(date: string, time: string): Date {
  return parseISO(toBrazilDateTimeISO(date, time));
}

export function nowInBrazil(): Date {
  return new Date(Date.now() + timeOffsetMs);
}

/**
 * Formata qualquer Date no horário de Brasília (America/Sao_Paulo).
 * Usa Intl.DateTimeFormat internamente, então funciona independente
 * do timezone da máquina que hospeda o bot.
 *
 * Formato padrão: dd/MM/yyyy HH:mm:ss
 */
export function formatInBrazil(date: Date | string, pattern?: string): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  if (Number.isNaN(d.getTime())) return '-';

  const parts = getBrazilDateParts(d);

  if (pattern === 'dd/MM/yyyy HH:mm') {
    return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`;
  }

  // default: dd/MM/yyyy HH:mm:ss
  return `${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}:${parts.second}`;
}

async function fetchHeaderDate(url: string): Promise<Date | null> {
  const isHttps = url.startsWith('https');
  const lib = isHttps ? https : http;

  return new Promise((resolve) => {
    const options: any = {
      method: 'HEAD',
      timeout: 3000,
    };

    if (isHttps) {
      options.rejectUnauthorized = false; // Ignora validação SSL se o relógio da máquina estiver dessincronizado
    }

    const request = lib.request(
      url,
      options,
      (response) => {
        const headerDate = response.headers.date;
        const parsed = headerDate ? new Date(headerDate) : null;
        response.resume();

        if (parsed && !Number.isNaN(parsed.getTime())) {
          resolve(parsed);
          return;
        }
        resolve(null);
      },
    );

    request.on('timeout', () => {
      request.destroy();
      resolve(null);
    });
    request.on('error', () => {
      resolve(null);
    });
    request.end();
  });
}

export async function trustedNow(): Promise<Date | null> {
  const sources = [
    'https://discord.com/api/v10/gateway',
    'http://www.google.com',
    'https://www.google.com',
    'http://www.cloudflare.com',
    'https://www.cloudflare.com',
    'http://www.apple.com',
    'https://www.apple.com'
  ];

  for (const source of sources) {
    try {
      const date = await fetchHeaderDate(source);
      if (date) {
        return date;
      }
    } catch {
      // tenta a próxima fonte
    }
  }

  return null;
}
