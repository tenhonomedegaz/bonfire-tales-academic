import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { Transaction } from '@/modules/transactions/entities/Transaction';

interface IRequest {
  email: string;
}

@injectable()
export class ShowAllActiveTransactionsByEmailUseCase implements IBaseUseCase {
  constructor(
    @inject('TransactionsRepository')
    private transactionsRepository: ITransactionsRepository,
  ) {}

  public async execute({ email }: IRequest): Promise<Transaction[]> {
    const activeSubscriptions = await this.transactionsRepository.findAllActiveByEmail(email);

    return activeSubscriptions;
  }
}
