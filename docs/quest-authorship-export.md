# Quest Authorship Evidence

## Exact Source Map

- `prisma/schema.prisma`: model `Quest`, PostgreSQL table `rpg_quests`.
- `id`: CUID quest identifier, not a sequential table number or a Discord message ID.
- `guildId`: Discord guild; `channelId`: mission channel, not publication message ID.
- `name`: mission name. There is no dedicated table-number or textual-master-name column.
- `questMaster`: master Discord user ID. `createdBy`: creator Discord user ID; keep separate.
- `questDate`, `createdAt`, `updatedAt`, `isPublished`, `status`: schedule and current publication state, not an immutable publication audit log.
- `createQuest.ts` sets both master and creator to interaction `user.id` for that command. Do not assume imported/historical rows always follow this invariant.
- `PublishQuestJob.ts` creates the mission channel, persists `channelId` and `isPublished`, then sends the announcement. It does NOT persist the sent message ID. Publication state alone therefore does not prove successful message delivery.
- `questEmbeds.ts` prints `Mestre: <@questMaster>`, `Criado por: <@createdBy>`, and quest ID in the footer. For these posts, the Discord message author is the bot, not the master.
- `DeleteQuestUseCase.ts` deletes the quest row and can delete its channel. Existing rows cannot establish complete historical authorship.
- `createPrivateQuest.ts` also sets `isPublished=true`, with `type='Privada'` and `tags=['privada']`. Published does NOT mean public.

## Site Read Surface (Source Inspection, Not Live Verification)

- `home.models.BotQuest` maps the SAME `rpg_quests` table, `managed=False`; it is an ORM mapping, not a separate replicated table.
- The inspected `home/db_access.py` allowlist does not expose `BotQuest`/`rpg_quests` or `UserProfile`. No functioning generic `/api/db/v1/<model>/` endpoint for these records was found. Do not invent a model alias.
- `/sistemas/missoes/` renders HTML from `BotQuest`: at most 100 rows, excludes finished by default, optional `status=finished`. It is not complete historical JSON evidence.
- Existing bot repository methods `findById`, `findByChannelId`, `findAllPublishedQuests`, `findAllUserQuests` are in-process methods, not HTTP API endpoints.
- `UserProfile.discord_user_id` is the site's unique, nullable Discord OAuth identity; `discord_username` is display information, not an ownership key. Future reviewed legacy associations should retain a Discord user ID and resolve it after successful Discord login, never by display-name equality. This tool writes no association.

## Offline Export

```powershell
node scripts/export-quest-authorship.cjs --help
node scripts/export-quest-authorship.cjs --input filtered-public.json --format messages --guild GUILD_ID --channel CHANNEL_ID --public-channel --limit 100 --dry-run
node scripts/export-quest-authorship.cjs --input filtered-public.json --format messages --guild GUILD_ID --channel CHANNEL_ID --public-channel --limit 100
node --test scripts/export-quest-authorship.test.cjs
```

Replace the ID placeholders with the explicitly authorized public guild/channel. Input is a JSON ARRAY, at most 1000 records / 10 MiB, format `messages` (Discord REST message objects) or `quests` (selected `rpg_quests` rows). Default processing limit is 100. CLI only reads that regular input file and writes JSON to stdout; dry-run emits counts/hash only. No service imports, database connection, environment loading, network, startup, scheduler or account writes occur, even on import.

Upstream acquisition must be separately authorized and limited: Discord `GET /api/v10/channels/{channel_id}/messages?limit=100` for the ONE public channel, or a filtered read of `rpg_quests` by `guildId`, `channelId`, `isPublished=true`, excluding private type/tags. For quest input only the fields in the map above are needed; do not collect participant data, descriptions, URLs with query secrets, emails, subscriptions or DMs. This tool deliberately does not fetch upstream data or read credentials. Publicness is attested by the caller; guild/channel checks do not establish channel visibility.

Output excludes raw content/descriptions, embeds, participant lists, arbitrary external URLs and author usernames. Explicit master labels and short mission titles are retained as necessary matching evidence. Message IDs and derived Discord public links identify reviewable evidence. Number extraction is only a `tableNumberHint`, never an authoritative spreadsheet match.

## Ownership Decision Boundary

All results have `autoLinkAllowed=false` and `historyComplete=false`. A single author among 100 exported posts is NOT proof that all posts belong to that user. `candidateDiscordUserId` / `singleUserWithinExport` describe only the observed subset. Bot/webhook authors are never substituted for a human; multiple authors, conflicting mentions or unresolved publication ownership prevent a single-user group candidate. Human-publisher evidence requires explicit `author.bot=false`; an omitted bot classification remains unresolved rather than guessing. Bot records with ID mentions but no textual master label cannot identify the spreadsheet's master name automatically.

Before parent enables an association, it must establish complete scope of all relevant publications, match the legacy master/mesa without ambiguous spelling or duplicate names, include unknown/unmatched evidence in review, and require exactly one consistent Discord identity. Deleted records/channels and legacy posts outside the captured scope remain limitations; preserve unresolved legacy rows without an owner. No XLSX ingestion, account creation, MM credit or future OAuth linkage is performed here.
