import { Member } from '@/modules/members/entities/Member';
import { Member as PrismaMember } from '@prisma/client';

export class PrismaMemberMapper {
  static toDomain(member: PrismaMember): Member {
    return {
      id: member.id,
      discordUserId: member.discordUserId,
      discordUserTag: member.discordUserTag,
      email: member.email,
      tokenSuperboost: member.tokenSuperboost,
      tokenXpBoost: member.tokenXpBoost,
      tokenMission: member.tokenMission,
      isModerator: member.isModerator,
      createdAt: member.createdAt,
      updatedAt: member.updatedAt,
    };
  }

  static toPersistence(member: Member): any {
    return {
      id: member.id,
      discordUserId: member.discordUserId,
      discordUserTag: member.discordUserTag,
      email: member.email,
      tokenSuperboost: member.tokenSuperboost,
      tokenXpBoost: member.tokenXpBoost,
      tokenMission: member.tokenMission,
      isModerator: member.isModerator,
      createdAt: member.createdAt,
      updatedAt: member.updatedAt,
    };
  }
}
