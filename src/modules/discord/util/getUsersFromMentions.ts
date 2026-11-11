export function getUsersFromMentions(message: string): string[] {
  const regexp = /<@!?(\d+)>/gm;
  const matches = message.matchAll(regexp);
  const users = [...matches].map((user) => user[1]);
  const uniqueUsers = [...new Set(users)];
  return uniqueUsers;
}
