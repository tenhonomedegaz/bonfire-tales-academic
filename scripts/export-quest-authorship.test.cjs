'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { exportEvidence } = require('./export-quest-authorship.cjs');
const G = '111111111111111111', C = '222222222222222222', U = '333333333333333333', V = '444444444444444444';
const options = { format: 'messages', guild: G, channel: C };
const message = (id, content, author = { id: U, bot: false }) => ({ id: String(id), guild_id: G, channel_id: C, content, author });

test('human publications produce a candidate, never a complete-history ownership decision', () => {
  const result = exportEvidence([message('555555555555555555', '**Mestre:** Bonfas\nMesa #123'),
    message('555555555555555556', 'Mestre: BONFAS\nMesa 124')], options);
  assert.equal(result.masters[0].candidateDiscordUserId, U);
  assert.equal(result.masters[0].publications, 2);
  assert.equal(result.evidence[0].tableNumberHint, '123');
  assert.equal(result.autoLinkAllowed, false);
  assert.equal(result.scope.historyComplete, false);
});

test('different authors and unknown authors prevent a single-user candidate', () => {
  for (const author of [{ id: V, bot: false }, { id: U, bot: true }, { id: U }]) {
    const result = exportEvidence([message('555555555555555555', 'Mestre: A'),
      message('555555555555555556', 'Mestre: A', author)], options);
    assert.equal(result.masters[0].candidateDiscordUserId, null);
  }
});

test('bot embed attributes the master mention, never the bot publisher', () => {
  const row = message('555555555555555555', '', { id: V, bot: true });
  row.embeds = [{ title: 'Missao 32', description: `Descricao: omitida\n🧙‍♂️ **Mestre:** <@${U}>\nSegredo: omitted` }];
  const result = exportEvidence([row], options);
  assert.equal(result.evidence[0].masterDiscordUserId, U);
  assert.equal(result.evidence[0].publisherDiscordUserId, null);
  assert.equal(result.evidence[0].masterLabel, null);
  assert.equal(result.masters.length, 0);
  assert.ok(!JSON.stringify(result).includes('Segredo'));
});

test('conflicting mentions or a human publishing for a different master require review', () => {
  for (const content of [`Mestre: A <@${V}>`, `Mestre: A <@${U}> <@${V}>`, 'Mestre: A\nMestre: B']) {
    const result = exportEvidence([message('555555555555555555', content)], options);
    assert.equal(result.evidence[0].identityConflict, true);
    assert.equal(result.evidence[0].candidateDiscordUserId, null);
  }
});

test('unrelated channels and explicit DMs are excluded', () => {
  const wrong = { ...message('555555555555555555', 'Mestre: A'), channel_id: V };
  const dm = { ...message('555555555555555556', 'Mestre: A'), guild_id: null };
  assert.equal(exportEvidence([wrong, dm], options).evidence.length, 0);
});

test('quests expose master and creator separately, exclude private/unpublished, omit PII', () => {
  const row = { id: 'cquest123', guildId: G, channelId: C, name: 'Mesa 15', questMaster: U,
    createdBy: V, isPublished: true, type: 'normal', description: 'private content',
    questPlayers: [{ email: 'private@example.test' }], tableUrl: 'https://example.test/?token=secret' };
  const result = exportEvidence([row, { ...row, id: 'private', type: 'Privada' },
    { ...row, id: 'draft', isPublished: false }], { ...options, format: 'quests' });
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0].masterDiscordUserId, U);
  assert.equal(result.evidence[0].creatorDiscordUserId, V);
  assert.equal(result.evidence[0].publisherDiscordUserId, null);
  assert.equal(result.evidence[0].masterLabel, null);
  assert.ok(!JSON.stringify(result).includes('private@example'));
  assert.ok(!JSON.stringify(result).includes('token=secret'));
});

test('row cap is explicit, invalid scopes and duplicate sources fail closed', () => {
  const rows = [message('555555555555555555', 'Mestre: A'), message('555555555555555556', 'Mestre: B')];
  assert.equal(exportEvidence(rows, { ...options, limit: 1 }).scope.truncated, true);
  assert.throws(() => exportEvidence([rows[0], rows[0]], options), /Duplicate/);
  assert.throws(() => exportEvidence(rows, { ...options, guild: '1' }));
  assert.throws(() => exportEvidence(rows, { ...options, limit: 1001 }));
  assert.throws(() => exportEvidence(Array(1001).fill(rows[0]), options));
});

test('master keys preserve accents rather than merging similar identities', () => {
  const result = exportEvidence([message('555555555555555555', 'Mestre: Jose'),
    message('555555555555555556', 'Mestre: Jose\u0301')], options);
  assert.equal(result.masters.length, 2);
});

test('non-announcements, webhook publishers and unrelated numbers do not imply identity', () => {
  const row = { ...message('555555555555555555', 'Mestre: A\nData 2026/11/04'), webhook_id: V };
  const result = exportEvidence([row, message('555555555555555556', 'Hello 2026')], options);
  assert.equal(result.evidence.length, 1);
  assert.equal(result.evidence[0].tableNumberHint, null);
  assert.equal(result.evidence[0].candidateDiscordUserId, null);
});

test('CLI dry-run reads a fixture, emits counts only and leaves its input unchanged', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'quest-authorship-'));
  const input = path.join(directory, 'public.json');
  const raw = JSON.stringify([message('555555555555555555', 'Mestre: Example')]);
  try {
    fs.writeFileSync(input, raw);
    const args = [path.join(__dirname, 'export-quest-authorship.cjs'), '--input', input,
      '--format', 'messages', '--guild', G, '--channel', C, '--public-channel'];
    const run = spawnSync(process.execPath, [...args, '--dry-run'], { encoding: 'utf8' });
    assert.equal(run.status, 0, run.stderr);
    const output = JSON.parse(run.stdout);
    assert.equal(output.dryRun, true);
    assert.equal(output.evidenceRows, 1);
    assert.equal(output.autoLinkAllowed, false);
    assert.equal(output.evidence, undefined);
    assert.ok(!run.stdout.includes(U));
    assert.equal(fs.readFileSync(input, 'utf8'), raw);
    assert.deepEqual(fs.readdirSync(directory), ['public.json']);
    const denied = spawnSync(process.execPath, args.filter(arg => arg !== '--public-channel'), { encoding: 'utf8' });
    assert.equal(denied.status, 1);
    assert.equal(denied.stdout, '');
  } finally {
    fs.unlinkSync(input);
    fs.rmdirSync(directory);
  }
});
