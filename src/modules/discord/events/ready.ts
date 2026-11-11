import { ActivityType, Client } from 'discord.js';

import { IBotEnhanced } from '@/modules/discord/types';

export interface IDiscordEventReady {
  name: string;
  once: boolean;
  execute: (bot: IBotEnhanced, client: Client) => Promise<void>;
}

export const readyEvent: IDiscordEventReady = {
  name: 'ready',
  once: true,
  execute: async (bot, client) => {
    try {
      client.user?.setUsername(bot.botName ?? 'BOT');
      // client.user?.setAvatar('URL or path');
      // client.user?.setStatus('online');

      client.user?.setPresence({
        afk: false,
        status: 'online',
        activities: [
          {
            type: ActivityType.Playing,
            name: `🎲`,
            // url: '',
          },
        ],
      });

      // List servers where bot is connected
      bot.logger.log('info', `${client.user?.tag} connected Guilds:`);

      client.guilds.cache.map(async (guild) => {
        bot.logger.log('info', ` > ${guild.id} - ${guild.name} - Members: ${guild.memberCount}`);
      });

      bot.logger.log('info', `Bot (${client.user?.tag}) is now up and running! 🚀`);
    } catch (error) {
      bot.logger.log('error', 'readyEvent', error);
    }
  },
};
