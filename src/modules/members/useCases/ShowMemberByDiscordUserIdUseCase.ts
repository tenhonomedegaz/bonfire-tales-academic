import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';

interface IRequest {
  discordUserId: string;
}

@injectable()
export class ShowMemberByDiscordUserIdUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute({ discordUserId }: IRequest): Promise<Member | null> {
    const member = await this.membersRepository.findByDiscordUserId(discordUserId);

    return member;
  }
}
