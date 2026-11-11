#!/usr/bin/env node
'use strict';

// Offline only: no bot startup, environment loading, database or Discord client.
const fs = require('node:fs');
const crypto = require('node:crypto');

const MAX_BYTES = 10 * 1024 * 1024;
const MAX_ROWS = 1000;
const snowflake = value => typeof value === 'string' && /^[0-9]{17,20}$/.test(value) ? value : null;
const short = value => typeof value === 'string' ? value.replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, 200) : null;
const key = value => value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLowerCase();

function tableNumber(text) {
  const match = text.match(/(?:\b(?:mesa|miss[aã]o)\s*(?:n[º°o.]\s*)?[:#-]?\s*|(?:^|\s)#)([0-9]{1,8})(?![0-9])/i);
  return match ? match[1] : null;
}

function masterFields(message) {
  const text = [message.content, ...(message.embeds || []).flatMap(embed => [
    embed.description, ...(embed.fields || []).filter(field => /^mestre\s*:?$/i.test(
      String(field.name || '').replace(/\*/g, '').trim())).map(field => 'Mestre: ' + field.value),
  ])].filter(value => typeof value === 'string').join('\n');
  const values = [...text.matchAll(/(?:^|\n)[^\p{L}\p{N}\n]*mestre\s*\*{0,2}\s*:\s*\*{0,2}\s*([^\n]+)/giu)]
    .map(match => match[1].replace(/\*\*/g, '').trim());
  const labels = [...new Set(values.map(value => short(value.replace(/<@!?[0-9]+>/g, '')
    .replace(/[()]/g, '').trim())).filter(Boolean))];
  const mentions = [...new Set(values.flatMap(value => [...value.matchAll(/<@!?([0-9]{17,20})>/g)]
    .map(match => match[1])))];
  return { masterLabel: labels.length === 1 ? labels[0] : null,
    masterDiscordUserId: mentions.length === 1 ? mentions[0] : null,
    ambiguous: labels.length > 1 || mentions.length > 1 };
}

function exportEvidence(rows, options) {
  if (!Array.isArray(rows) || rows.length > MAX_ROWS) throw new Error('Input must be an array of at most 1000 rows; filter upstream.');
  if (!snowflake(options.guild) || !snowflake(options.channel)) throw new Error('Explicit guild and authorized public channel IDs required.');
  if (!['quests', 'messages'].includes(options.format)) throw new Error('Format must be quests or messages.');
  const limit = options.limit === undefined ? 100 : Number(options.limit);
  if (!Number.isInteger(limit) || limit < 1 || limit > MAX_ROWS) throw new Error('Limit must be between 1 and 1000.');
  const evidence = [], seen = new Set();
  let excluded = 0, scanned = 0;
  for (const row of rows.slice(0, limit)) {
    scanned++;
    if (!row || typeof row !== 'object' || Array.isArray(row)) throw new Error('Invalid row.');
    const quests = options.format === 'quests';
    const guild = quests ? row.guildId : row.guild_id;
    const channel = quests ? row.channelId : row.channel_id;
    // Discord REST message pages may omit guild_id; the supplied channel is mandatory.
    if (channel !== options.channel || (guild !== undefined && guild !== options.guild)
        || (quests && guild !== options.guild)) { excluded++; continue; }
    if (quests && (row.isPublished !== true || /privad[ao]|private/i.test(row.type || '')
        || (Array.isArray(row.tags) && row.tags.some(tag => /privad[ao]|private/i.test(tag))))) {
      excluded++; continue;
    }
    const id = quests && typeof row.id === 'string' && /^[a-zA-Z0-9_-]{1,40}$/.test(row.id)
      ? row.id : !quests ? snowflake(row.id) : null;
    if (!id) throw new Error('Missing or invalid source ID.');
    if (seen.has(id)) throw new Error('Duplicate source ID; deduplicate and review upstream.');
    seen.add(id);
    const title = short(quests ? row.name : row.embeds?.[0]?.title);
    const fields = quests ? { masterLabel: null, masterDiscordUserId: snowflake(row.questMaster), ambiguous: false }
      : masterFields(row);
    const publisher = !quests && row.author?.bot === false && !row.webhook_id ? snowflake(row.author.id) : null;
    const number = tableNumber([title, !quests ? row.content : ''].filter(Boolean).join('\n'));
    // Do not export arbitrary conversation as an announcement.
    if (!quests && !fields.masterLabel && !fields.masterDiscordUserId && !fields.ambiguous && !number) {
      excluded++; continue;
    }
    const conflict = fields.ambiguous || Boolean(publisher && fields.masterDiscordUserId && publisher !== fields.masterDiscordUserId);
    evidence.push({
      source: quests ? 'rpg_quests' : 'public_discord_message', sourceId: id,
      guildId: options.guild, channelId: options.channel,
      messageUrl: quests ? null : `https://discord.com/channels/${options.guild}/${options.channel}/${id}`,
      questId: quests ? id : null, title, tableNumberHint: number,
      masterLabel: fields.masterLabel, masterKey: fields.masterLabel ? key(fields.masterLabel) : null,
      masterDiscordUserId: fields.masterDiscordUserId,
      creatorDiscordUserId: quests ? snowflake(row.createdBy) : null,
      publisherDiscordUserId: publisher,
      identityConflict: conflict,
      candidateDiscordUserId: conflict ? null : fields.masterDiscordUserId || publisher,
    });
  }
  const groups = new Map();
  for (const row of evidence.filter(row => row.masterKey)) {
    const group = groups.get(row.masterKey) || { masterKey: row.masterKey, labels: new Set(), rows: [] };
    group.labels.add(row.masterLabel); group.rows.push(row); groups.set(row.masterKey, group);
  }
  return {
    schema: 1, scope: { format: options.format, guildId: options.guild, channelId: options.channel,
      inputRows: rows.length, scannedRows: scanned, excludedRows: excluded, limit,
      truncated: rows.length > limit, historyComplete: false, publicChannelAttestedByCaller: true },
    autoLinkAllowed: false,
    reason: 'A bounded/offline export cannot prove all historical publications. Review full scope and OAuth identity before linking.',
    evidence,
    masters: [...groups.values()].map(group => {
      const ids = [...new Set(group.rows.map(row => row.candidateDiscordUserId).filter(Boolean))].sort();
      const unresolved = group.rows.filter(row => !row.candidateDiscordUserId).length;
      return { masterKey: group.masterKey, labels: [...group.labels].sort(), publications: group.rows.length,
        observedDiscordUserIds: ids, unresolvedPublications: unresolved,
        singleUserWithinExport: ids.length === 1 && unresolved === 0,
        candidateDiscordUserId: ids.length === 1 && unresolved === 0 ? ids[0] : null,
        autoLinkAllowed: false };
    }).sort((a, b) => a.masterKey.localeCompare(b.masterKey)),
  };
}

function main(argv) {
  const options = {};
  const allowed = new Set(['input', 'format', 'guild', 'channel', 'limit']);
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--dry-run') { options.dryRun = true; continue; }
    if (arg === '--public-channel') { options.publicChannel = true; continue; }
    if (arg === '--help') {
      process.stdout.write('Offline JSON only; no database/network/.env.\nnode scripts/export-quest-authorship.cjs --input filtered.json --format quests|messages --guild ID --channel ID --public-channel [--limit 100] [--dry-run]\nOnly an explicitly authorized public channel may be supplied. JSON goes to stdout; dry-run prints counts only.\n');
      return;
    }
    const name = arg.slice(2);
    if (!arg.startsWith('--') || !allowed.has(name) || !argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error('Invalid arguments; use --help.');
    if (options[name] !== undefined) throw new Error('Duplicate argument.');
    options[name] = argv[++i];
  }
  if (!options.input || !options.publicChannel) throw new Error('Input and --public-channel acknowledgement required.');
  const fd = fs.openSync(options.input, 'r');
  let raw;
  try {
    if (!fs.fstatSync(fd).isFile()) throw new Error('Input must be a regular JSON file.');
    const buffer = Buffer.alloc(MAX_BYTES + 1);
    let size = 0, count;
    while (size < buffer.length && (count = fs.readSync(fd, buffer, size, buffer.length - size, null))) size += count;
    if (size > MAX_BYTES) throw new Error('Input exceeds 10 MiB.');
    raw = buffer.subarray(0, size);
  } finally { fs.closeSync(fd); }
  const result = exportEvidence(JSON.parse(raw.toString('utf8').replace(/^\uFEFF/, '')), options);
  result.inputSha256 = crypto.createHash('sha256').update(raw).digest('hex');
  const output = options.dryRun ? { schema: result.schema, dryRun: true, scope: result.scope,
    evidenceRows: result.evidence.length, masterGroups: result.masters.length,
    autoLinkAllowed: false, inputSha256: result.inputSha256 } : result;
  process.stdout.write(JSON.stringify(output, null, 2) + '\n');
}

module.exports = { exportEvidence, main };
if (require.main === module) {
  try { main(process.argv.slice(2)); }
  catch { process.stderr.write('Export failed: invalid input/scope. Check --help; no database or network operation was attempted.\n'); process.exitCode = 1; }
}
