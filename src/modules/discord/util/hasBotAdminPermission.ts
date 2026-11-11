import { bonfireBotAdminUserIds, bonfireRoles } from '@/config/bonfire';

export function isBotRootAdmin(userId: string): boolean {
  return bonfireBotAdminUserIds.includes(userId);
}

export function hasBotAdminPermission(userId: string, member: any): boolean {
  if (isBotRootAdmin(userId)) {
    return true;
  }

  return !!(member?.roles as any)?.cache?.some(
    (role: any) => role.name === bonfireRoles.adminRoleName,
  );
}
