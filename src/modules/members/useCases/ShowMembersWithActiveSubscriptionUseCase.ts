import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { IMembersRepository } from '@/modules/members/repositories/IMembersRepository';
import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { Member } from '@/modules/members/entities/Member';

@injectable()
export class ShowMembersWithActiveSubscriptionUseCase implements IBaseUseCase {
  constructor(
    @inject('MembersRepository')
    private membersRepository: IMembersRepository,
    @inject('TransactionsRepository')
    private transactionsRepository: ITransactionsRepository,
  ) {}

  public async execute(): Promise<Member[]> {
    const activeTransactions = await this.transactionsRepository.findAllActive();

    const emailsWithActiveSubscription = [
      ...new Set(activeTransactions.map((transaction) => transaction.email)),
    ];

    const membersWithActiveTransactions = await this.membersRepository.findAllByEmails({
      emails: emailsWithActiveSubscription,
    });

    return membersWithActiveTransactions;
  }
}
