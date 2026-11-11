import { Member } from '@/modules/members/entities/Member';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { PrismaMemberMapper } from '@/modules/members/repositories/prisma/mappers/PrismaMemberMapper';
import {
  ICreateMemberDTO,
  IFindAllByEmailsDTO,
  IFindByDiscordUserIdOrEmailDTO,
} from '@/modules/members/dtos';
import { prisma } from '@/shared/infra/database/prisma';

export class PrismaMembersRepository implements IMembersRepository {
  public async create(data: ICreateMemberDTO): Promise<Member> {
    const member = await prisma.member.create({
      data,
    });
    return PrismaMemberMapper.toDomain(member);
  }

  public async save(data: Member): Promise<Member> {
    const raw = PrismaMemberMapper.toPersistence(data);
    const { id, ...updateData } = raw;

    const member = await prisma.member.update({
      where: { id },
      data: updateData,
    });

    if (!member) {
      throw new Error('Usuário inválido');
    }

    return PrismaMemberMapper.toDomain(member);
  }

  public async findById(id: string): Promise<Member | null> {
    const member = await prisma.member.findUnique({
      where: { id },
    });
    return member ? PrismaMemberMapper.toDomain(member) : null;
  }

  public async findByDiscordUserId(discordUserId: string): Promise<Member | null> {
    const member = await prisma.member.findUnique({
      where: { discordUserId },
    });
    return member ? PrismaMemberMapper.toDomain(member) : null;
  }

  public async findByDiscordUserIdOrEmail({
    discordUserId,
    email,
  }: IFindByDiscordUserIdOrEmailDTO): Promise<Member | null> {
    const member = await prisma.member.findFirst({
      where: {
        OR: [{ discordUserId }, { email }],
      },
    });
    return member ? PrismaMemberMapper.toDomain(member) : null;
  }

  public async findAllByEmails({ emails }: IFindAllByEmailsDTO): Promise<Member[]> {
    const members = await prisma.member.findMany({
      where: {
        email: { in: emails },
      },
    });
    return members.map(PrismaMemberMapper.toDomain);
  }

  public async findAllWithVerificationDisabled(): Promise<Member[]> {
    const members = await prisma.member.findMany({
      where: {
        OR: [{ skipValidation: true }, { isAdmin: true }],
      },
    });
    return members.map(PrismaMemberMapper.toDomain);
  }
}
