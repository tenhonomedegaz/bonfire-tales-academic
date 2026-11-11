import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';

interface IRequest {
  discordUserId: string;
  email: string;
}

@injectable()
export class ShowMemberByDiscordUserIdOrEmailUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute({ discordUserId, email }: IRequest): Promise<Member | null> {
    const member = await this.membersRepository.findByDiscordUserIdOrEmail({
      discordUserId,
      email: email.toLowerCase(),
    });

    return member;
  }
}
