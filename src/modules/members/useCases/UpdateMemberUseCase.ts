import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { Member } from '@/modules/members/entities/Member';

type IRequest = Member;

@injectable()
export class UpdateMemberUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute(member: IRequest): Promise<Member> {
    const updatedMember = await this.membersRepository.save(member);
    return updatedMember;
  }
}
