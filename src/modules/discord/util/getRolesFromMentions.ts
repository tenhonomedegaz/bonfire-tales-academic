export function getRolesFromMentions(message: string): string[] {
  const regexp = /<@&?(\d+)>/gm;
  const matches = message.matchAll(regexp);
  const roles = [...matches].map((role) => role[1]);
  const uniqueRoles = [...new Set(roles)];
  return uniqueRoles;
}
