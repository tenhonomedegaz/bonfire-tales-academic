import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';
import { bonfireTokens } from '@/config/bonfire';

type IRequest = {
  discordUserId: string;
  tokenType: string;
};

@injectable()
export class UseMemberTokenUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute({ discordUserId, tokenType }: IRequest): Promise<Member | null> {
    if (!bonfireTokens.map((token) => token.id).includes(tokenType)) {
      throw new Error('Tipo de token inválido');
    }

    const member = await this.membersRepository.findByDiscordUserId(discordUserId);

    if (!member) {
      throw new Error('Usuário não localizado');
    }

    if (tokenType === 'superboost' && member.tokenSuperboost <= 0) {
      throw new Error(`Você não possui tokens de Superboost para serem utilizados`);
    }

    if (tokenType === 'boost' && member.tokenXpBoost <= 0) {
      throw new Error(`Você não possui tokens de Boost para serem utilizados`);
    }

    if (tokenType === 'missão' && member.tokenMission <= 0) {
      throw new Error(`Você não possui tokens de Missão Especial para serem utilizados`);
    }

    member.tokenSuperboost = tokenType === 'superboost' ? member.tokenSuperboost - 1 : member.tokenSuperboost;
	member.tokenXpBoost = tokenType === 'boost' ? member.tokenXpBoost - 1 : member.tokenXpBoost;
    member.tokenMission = tokenType === 'missão' ? member.tokenMission - 1 : member.tokenMission;

    await this.membersRepository.save(member);

    return member;
  }
}
