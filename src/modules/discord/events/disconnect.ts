import { Client } from 'discord.js';

import { IBotEnhanced } from '@/modules/discord/types';

export interface IDiscordEventDisconnect {
  name: string;
  once: boolean;
  execute: (bot: IBotEnhanced, client: Client) => Promise<void>;
}

export const disconnectEvent: IDiscordEventDisconnect = {
  name: 'disconnect',
  once: false,
  execute: async (bot, client) => {
    try {
      bot.logger.log('warn', `Bot (${client.user?.tag}) disconnected...`);
    } catch (error) {
      bot.logger.log('error', 'disconnectEvent', error);
    }
  },
};
