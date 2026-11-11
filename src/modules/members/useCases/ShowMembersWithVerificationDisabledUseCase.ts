import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';

@injectable()
export class ShowMembersWithVerificationDisabledUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute(): Promise<Member[]> {
    const membersWithVerificationDisabled =
      await this.membersRepository.findAllWithVerificationDisabled();

    return membersWithVerificationDisabled;
  }
}
