import { Guild } from 'discord.js';

export function isGuildMemberUserId(userId: string, guild: Guild) {
  const guildMember = guild.members.cache.find(
    (member) => member.id === userId && !member.user.bot,
  );

  return !!guildMember;
}
