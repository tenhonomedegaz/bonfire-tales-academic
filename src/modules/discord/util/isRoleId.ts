import { Guild } from 'discord.js';

export function isRoleId(roleId: string, guild: Guild) {
  const guildRole = guild.roles.cache.find((role) => role.id === roleId);

  return !!guildRole;
}
