import { Guild, TextChannel } from 'discord.js';

import { bonfireChannels } from '@/config/bonfire';

const LOG_CHANNEL_ALIASES = [
  bonfireChannels.logChannelName,
  '🔧configuração-bots',
  'configuração-bots',
  'configuracao-bots',
];

function normalizeChannelName(channelName: string): string {
  return channelName
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\w-]/g, '')
    .toLowerCase();
}

export function findBonfireLogChannel(guild: Guild): TextChannel | undefined {
  const normalizedAliases = LOG_CHANNEL_ALIASES.map(normalizeChannelName);

  return guild.channels.cache.find((channel) => {
    if (!channel.isTextBased()) {
      return false;
    }

    const normalizedChannelName = normalizeChannelName(channel.name);
    return normalizedAliases.includes(normalizedChannelName);
  }) as TextChannel | undefined;
}
