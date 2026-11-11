import { injectable, inject } from 'tsyringe';

import { IBaseUseCase } from '@/shared/useCases/IBaseUseCase';
import { ITransactionsRepository } from '@/modules/transactions/repositories/ITransactionsRepository';
import { Transaction } from '@/modules/transactions/entities/Transaction';
import { ICreateTransactionDTO } from '@/modules/transactions/dtos';
import { isValidEmail } from '@/shared/util/validators';

type IRequest = ICreateTransactionDTO;

@injectable()
export class CreateTransactionUseCase implements IBaseUseCase {
  constructor(
    @inject('TransactionsRepository')
    private transactionsRepository: ITransactionsRepository,
  ) {}

  public async execute({
    transactionCode,
    transactionSource,
    paymentDate,
    expirationDate,
    subscriptionPlan,
    subscriptionPeriod,
    subscriptionReference,
    status,
    grossAmount,
    netAmount,
    name,
    email,
    comments,
    claimed,
    claimedAt,
  }: IRequest): Promise<Transaction> {

    if (!isValidEmail(email)) {
      throw new Error(`Email ${email} inválido`);
    }

    const existingTransaction = await this.transactionsRepository.findByTransactionCode(
      transactionCode,
    );

    if (existingTransaction) {
      throw new Error('Transação já existente');
    }

    let transaction;

    try {
      transaction = await this.transactionsRepository.create({
        transactionCode,
        transactionSource,
        paymentDate,
        expirationDate,
        subscriptionPlan,
        subscriptionPeriod,
        subscriptionReference,
        status,
        grossAmount,
        netAmount,
        name,
        email,
        comments,
        claimed,
        claimedAt,
      });
    } catch (error: any) {
      console.error("🔥 Mongoose CREATE ERROR FULL DETAILS: name:", error?.name);
	  console.error("🔥 Mongoose CREATE ERROR message:", error?.message);
	  console.error("🔥 Mongoose CREATE ERROR stack:", error?.stack);
	  if (error?.errors) {
		console.error("🔥 Mongoose validation errors:");
		for (const key of Object.keys(error.errors)) {
		  console.error(`  - ${key}:`, error.errors[key].message, error.errors[key]);
		}
	  }
	  try {
		console.error("🔥 Full error (safe JSON):", JSON.stringify(error, Object.getOwnPropertyNames(error), 2));
	  } catch (e) {
		console.error("🔥 Failed to stringify error", e);
	  }
	  
      throw error;
    }

    return transaction;
  }
}