import { Member } from '@/modules/members/entities/Member';
import {
  ICreateMemberDTO,
  IFindAllByEmailsDTO,
  IFindByDiscordUserIdOrEmailDTO,
} from '@/modules/members/dtos';

export interface IMembersRepository {
  create(data: ICreateMemberDTO): Promise<Member>;
  save(data: Member): Promise<Member>;
  findById(id: string): Promise<Member | null>;

  findByDiscordUserId(discordUserId: string): Promise<Member | null>;
  findByDiscordUserIdOrEmail({
    discordUserId,
    email,
  }: IFindByDiscordUserIdOrEmailDTO): Promise<Member | null>;
  findAllByEmails({ emails }: IFindAllByEmailsDTO): Promise<Member[]>;
  findAllWithVerificationDisabled(): Promise<Member[]>;
}
