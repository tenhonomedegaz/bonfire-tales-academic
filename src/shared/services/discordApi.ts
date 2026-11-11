import { REST } from '@discordjs/rest';

import { env } from '@/shared/env';

export const discordApi = new REST({ version: '10' }).setToken(env.DISCORD_BOT_TOKEN);
