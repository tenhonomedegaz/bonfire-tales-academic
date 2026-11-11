/* eslint-disable no-await-in-loop */
/* eslint-disable no-restricted-syntax */
import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { Member } from '@/modules/members/entities/Member';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { bonfireProducts } from '@/config/bonfire';
import { nowInBrazil } from '@/shared/util/dateTime';


type IRequest = Member;

@injectable()
export class ClaimTransactionsTokensUseCase implements IBaseUseCase {
  constructor(
    @inject('TransactionsRepository')
    private transactionsRepository: ITransactionsRepository,

    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
  ) {}

  public async execute(member: IRequest): Promise<Member> {
    const updatedMember = { ...member };

    const unclaimedTransactions = await this.transactionsRepository.findUnclaimedUserTransactions({
      email: member.email,
    });

    for (const unclaimedTransaction of unclaimedTransactions) {
      const product = bonfireProducts.find(
        (item) => item.subscriptionPlanName === unclaimedTransaction.subscriptionPlan,
      );
      const tokenMissionToAdd = product?.tokenMission ? product.tokenMission : 0;
      const tokenXpBoostToAdd = product?.tokenXpBoost ? product.tokenXpBoost : 0;
      const tokenSuperboostToAdd = product?.tokenSuperboost ? product.tokenSuperboost : 0;

      updatedMember.tokenMission += tokenMissionToAdd;
      updatedMember.tokenXpBoost += tokenXpBoostToAdd;
	  updatedMember.tokenSuperboost += tokenSuperboostToAdd;

      unclaimedTransaction.claimed = true;
      unclaimedTransaction.claimedAt = nowInBrazil();
      await this.transactionsRepository.save(unclaimedTransaction);

      await this.membersRepository.save(updatedMember);
    }

    return updatedMember;
  }
}
