import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';
import { ICreateMemberDTO } from '@/modules/members/dtos';

type IRequest = ICreateMemberDTO;

@injectable()
export class CreateMemberUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute({
    discordUserId,
    discordUserTag,
    email,
	tokenSuperboost,
    tokenXpBoost,
    tokenMission,
    isModerator,
  }: IRequest): Promise<Member> {
    const existingMember = await this.membersRepository.findByDiscordUserIdOrEmail({
      discordUserId,
      email,
    });

    if (existingMember) {
      throw new Error(
        `Não é possível cadastrar esse email pois ele já está associado com um usuário do discord`,
      );
    }

    const newMember = await this.membersRepository.create({
      discordUserId,
      discordUserTag,
      email: email.toLowerCase(),
	  tokenSuperboost,
      tokenXpBoost,
      tokenMission,
      isModerator,
    });

    return newMember;
  }
}
